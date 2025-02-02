import pytest
from unittest.mock import patch, MagicMock
import boto3
from edx_argoutils.s3 import get_s3_client, delete_s3_directory, delete_object_from_s3, list_object_keys_from_s3, write_report_to_s3, get_s3_url, get_s3_path_for_date

# Test `get_s3_client` function
@patch('boto3.client')
def test_get_s3_client_with_credentials(mock_boto_client):
    mock_s3_client = MagicMock()
    mock_boto_client.return_value = mock_s3_client

    credentials = {'AccessKeyId': 'AKIA...', 'SecretAccessKey': 'SECRET...', 'SessionToken': 'SESSION...'}
    s3_client = get_s3_client(credentials)

    mock_boto_client.assert_called_once_with(
        's3', aws_access_key_id='AKIA...', aws_secret_access_key='SECRET...', aws_session_token='SESSION...'
    )
    assert s3_client == mock_s3_client


@patch('boto3.client')
def test_get_s3_client_without_credentials(mock_boto_client):
    mock_s3_client = MagicMock()
    mock_boto_client.return_value = mock_s3_client

    s3_client = get_s3_client()

    mock_boto_client.assert_called_once_with('s3')
    assert s3_client == mock_s3_client


# Test `delete_s3_directory` function
@patch('boto3.client')
@patch('edx_argoutils.s3.list_object_keys_from_s3')
def test_delete_s3_directory(mock_list_keys, mock_boto_client):
    mock_s3_client = MagicMock()
    mock_boto_client.return_value = mock_s3_client
    mock_list_keys.return_value = ['file1.txt', 'file2.txt']

    bucket = 'my-bucket'
    prefix = 'folder/'
    credentials = {'AccessKeyId': 'AKIA...', 'SecretAccessKey': 'SECRET...', 'SessionToken': 'SESSION...'}

    delete_s3_directory(bucket, prefix, credentials)

    mock_list_keys.assert_called_once_with(bucket, prefix, credentials)
    mock_s3_client.delete_objects.assert_called_once_with(
        Bucket=bucket,
        Delete={'Objects': [{'Key': 'file1.txt'}, {'Key': 'file2.txt'}]}
    )


# Test `delete_object_from_s3` function
@patch('boto3.client')
def test_delete_object_from_s3(mock_boto_client):
    mock_s3_client = MagicMock()
    mock_boto_client.return_value = mock_s3_client

    bucket = 'my-bucket'
    key = 'folder/file.txt'
    credentials = {'AccessKeyId': 'AKIA...', 'SecretAccessKey': 'SECRET...', 'SessionToken': 'SESSION...'}

    delete_object_from_s3(key, bucket, credentials)

    mock_s3_client.delete_object.assert_called_once_with(Bucket=bucket, Key=key)


# Test `list_object_keys_from_s3` function
@patch('boto3.client')
def test_list_object_keys_from_s3(mock_boto_client):
    mock_s3_client = MagicMock()
    mock_boto_client.return_value = mock_s3_client

    # Simulate the first page of objects
    mock_s3_client.list_objects_v2.return_value = {
        'Contents': [{'Key': 'file1.txt'}, {'Key': 'file2.txt'}],
        'IsTruncated': True,
        'NextContinuationToken': 'next-token'
    }

    # Simulate the second page of objects
    mock_s3_client.list_objects_v2.side_effect = [
        {'Contents': [{'Key': 'file1.txt'}, {'Key': 'file2.txt'}], 'IsTruncated': True, 'NextContinuationToken': 'next-token'},
        {'Contents': [{'Key': 'file3.txt'}], 'IsTruncated': False}
    ]

    bucket = 'my-bucket'
    prefix = 'folder/'
    credentials = {'AccessKeyId': 'AKIA...', 'SecretAccessKey': 'SECRET...', 'SessionToken': 'SESSION...'}

    keys = list_object_keys_from_s3(bucket, prefix, credentials)

    mock_s3_client.list_objects_v2.assert_any_call(Bucket=bucket, Prefix=prefix)
    assert keys == ['file1.txt', 'file2.txt', 'file3.txt']


# Test `write_report_to_s3` function
@patch('boto3.client')
@patch('edx_argoutils.s3.get_s3_path_for_date')
def test_write_report_to_s3(mock_get_s3_path, mock_boto_client):
    mock_s3_client = MagicMock()
    mock_boto_client.return_value = mock_s3_client
    mock_get_s3_path.return_value = 'folder/report.json'

    download_results = ('report', '{"key": "value"}')
    s3_bucket = 'my-bucket'
    s3_path = 'folder/'
    credentials = {'AccessKeyId': 'AKIA...', 'SecretAccessKey': 'SECRET...', 'SessionToken': 'SESSION...'}

    file_path = write_report_to_s3(download_results, s3_bucket, s3_path, credentials)

    mock_s3_client.put_object.assert_called_once_with(
        Bucket=s3_bucket,
        Key='folder/report.json',
        Body='{"key": "value"}',
        ContentType='application/json'
    )
    assert file_path == 'folder/report.json'


# Test `get_s3_url` function
def test_get_s3_url():
    bucket = 'my-bucket'
    path = 'folder/report.json'
    expected_url = 's3://my-bucket/folder/report.json'

    s3_url = get_s3_url(bucket, path)

    assert s3_url == expected_url


# Test `get_s3_path_for_date` function
def test_get_s3_path_for_date():
    filename = 'report'
    expected_path = 'report/report.json'

    s3_path = get_s3_path_for_date(filename)

    assert s3_path == expected_path
