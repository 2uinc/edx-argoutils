"""
Tests for sitemap functions.
pytest test_sitemap.py
"""

import json
import unittest
from unittest.mock import Mock, patch
import requests
from edx_argoutils.sitemap import fetch_sitemap, fetch_sitemap_urls, write_sitemap_to_s3
from datetime import datetime, timezone


SCRAPED_AT = '2025-02-06'


class TestSitemapTasks(unittest.TestCase):

    @patch.object(requests, 'get')
    def test_fetch_sitemap_urls(self, mockget):
        # Mock the response from requests.get
        mockresponse = Mock()
        mockget.return_value = mockresponse
        mockresponse.text = """<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <sitemap>
                <loc>https://www.foo.com/sitemap-0.xml</loc>
            </sitemap>
            <sitemap>
                <loc>https://www.foo.com/sitemap-1.xml</loc>
            </sitemap>
        </sitemapindex>
        """

        # Expected output for the mock sitemap index response
        expected_output = ['https://www.foo.com/sitemap-0.xml', 'https://www.foo.com/sitemap-1.xml']

        # Call the function (directly, without Prefect context)
        result = fetch_sitemap_urls(sitemap_index_url='dummy_url')

        # Check if the result matches the expected output
        self.assertEqual(result, expected_output)

    @patch('edx_argoutils.common.get_date')
    @patch.object(requests, 'get')
    def test_fetch_sitemap(self, mockget, mock_get_date):
        mock_get_date.return_value = '2025-02-06'

        # Mock the response from requests.get
        mockresponse = Mock()
        mockget.return_value = mockresponse
        mockresponse.text = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
                xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">
            <url>
                <loc>https://www.foo.come/terms-service</loc>
                <changefreq>daily</changefreq>
                <priority>0.7</priority>
            </url>
            <url>
                <loc>https://www.foo.come/policy</loc>
                <changefreq>daily</changefreq>
                <priority>0.7</priority>
            </url>
            <url>
                <loc>https://www.foo.come/policy/security</loc>
                <changefreq>daily</changefreq>
                <priority>0.7</priority>
            </url>
        </urlset>
        """

        # Expected output for the mock sitemap response
        expected_output = [
            {'scraped_at': SCRAPED_AT, 'url': 'https://www.foo.come/terms-service'},
            {'scraped_at': SCRAPED_AT, 'url': 'https://www.foo.come/policy'},
            {'scraped_at': SCRAPED_AT, 'url': 'https://www.foo.come/policy/security'},
        ]

        # Fetch sitemap while mocking get_date to ensure consistent SCRAPED_AT timestamp
        sitemap_url = 'https://www.foo.com/sitemap-0.xml'
        sitemap_filename, sitemap_json = fetch_sitemap(sitemap_url=sitemap_url)

        result_json = json.loads(sitemap_json)
        for entry in result_json:
            entry['scraped_at'] = entry['scraped_at'].split('T')[0]  # Remove time part if present
        # Check if the result matches the expected output
        self.assertEqual((sitemap_filename, json.loads(sitemap_json)), ('sitemap-0', expected_output))

    @patch('edx_argoutils.common.get_date', return_value=datetime.now().strftime('%Y-%m-%d'))  # Mocking expected date
    @patch('boto3.client')  # Mocking the boto3 S3 client
    def test_write_sitemap_to_s3(self, mock_boto_client, mock_get_date):
        mock_s3_client = Mock()
        mock_s3_client.put_object = Mock()
        mock_boto_client.return_value = mock_s3_client

        # Retrieve the mocked current date (which is returned by get_date function)
        today = mock_get_date.return_value

        result = write_sitemap_to_s3(
            sitemap_data=('sitemap_content', '{"urlset": []}'),
            s3_bucket='test-bucket',
            s3_path='dev/sitemaps/',
            credentials={'AccessKeyId': 'AK123', 'SecretAccessKey': 'SAK', 'SessionToken': '987654321'}
        )

        # Verify the put_object method of the mock S3 client was called with the expected parameters
        mock_boto_client.return_value.put_object.assert_called_once_with(
            Bucket='test-bucket',
            Key=f'dev/sitemaps/{today}/sitemap_content.json',
            Body='{"urlset": []}',
            ContentType='application/json'
        )
        # Verify the result returned by the function is correct
        self.assertEqual(result, f'{today}/sitemap_content.json')


if __name__ == '__main__':
    unittest.main()
