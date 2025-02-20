"""
Tests for paypal SFTP.
"""
import pytest
import datetime
import json
from unittest.mock import MagicMock, patch
from edx_argoutils.paypal import (
    check_paypal_report,
    format_paypal_report,
    get_paypal_filename,
    fetch_paypal_report,
    RemoteFileNotFoundError,
)


@pytest.fixture
def mock_sftp():
    """Fixture to create a mock SFTP connection."""
    mock_sftp = MagicMock()
    return mock_sftp


def test_check_paypal_report_valid(mock_sftp):
    """Test that check_paypal_report passes when SB and SF row counts match."""
    mock_sftp.open.return_value.readlines.return_value = [
        "HEADER\n", "HEADER\n", "HEADER\n",
        "CH,Amount\n",
        "SB,100\n",
        "SB,200\n",
        "SF,2\n",
    ]
    check_paypal_report(mock_sftp, "test.csv", "Amount")


def test_check_paypal_report_invalid(mock_sftp):
    """Test that check_paypal_report raises an error when SB and SF row counts do not match."""
    mock_sftp.open.return_value.readlines.return_value = [
        "HEADER\n", "HEADER\n", "HEADER\n",
        "CH,Amount\n",
        "SB,100\n",
        "SB,200\n",
        "SF,3\n",
    ]
    with pytest.raises(Exception, match="Paypal row counts do not match"):
        check_paypal_report(mock_sftp, "test.csv", "Amount")


def test_check_paypal_report_empty_file(mock_sftp):
    """Test handling of empty file - should return empty list after header."""
    mock_sftp.open.return_value.readlines.return_value = [
        "HEADER\n", "HEADER\n", "HEADER\n",
        "CH,Amount\n",
    ]
    # This should not raise an error as per the original implementation
    # The file has headers but no data rows
    check_paypal_report(mock_sftp, "test.csv", "Amount")


def test_check_paypal_report_missing_sf_row(mock_sftp):
    """Test handling of missing SF row."""
    mock_sftp.open.return_value.readlines.return_value = [
        "HEADER\n", "HEADER\n", "HEADER\n",
        "CH,Amount\n",
        "SB,100\n",
        "SB,200\n",
    ]
    with pytest.raises(Exception, match="Paypal row counts do not match for test.csv! Rows found: 2, Rows expected: 0"):
        check_paypal_report(mock_sftp, "test.csv", "Amount")

def test_check_paypal_report_invalid_column(mock_sftp):
    """Test handling of invalid check column name."""
    mock_sftp.open.return_value.readlines.return_value = [
        "HEADER\n", "HEADER\n", "HEADER\n",
        "CH,Amount\n",
        "SB,100\n",
        "SF,1\n",
    ]
    with pytest.raises(KeyError):
        check_paypal_report(mock_sftp, "test.csv", "InvalidColumn")


def test_format_paypal_report(mock_sftp):
    """Test that format_paypal_report correctly formats PayPal reports."""
    mock_sftp.open.return_value.readlines.return_value = [
        "HEADER\n", "HEADER\n", "HEADER\n",
        "CH,Amount\n",
        "SB,100\n",
        "SB,200\n",
        "SF,2\n",
    ]
    result = format_paypal_report(mock_sftp, "test.csv", "2025-02-02")
    expected_output = json.dumps([
        {"CH": "SB", "Amount": "100", "report_date": "2025-02-02"},
        {"CH": "SB", "Amount": "200", "report_date": "2025-02-02"},
    ])
    assert result == expected_output


def test_format_paypal_report_empty_file(mock_sftp):
    """Test formatting of empty file - should return empty JSON array."""
    mock_sftp.open.return_value.readlines.return_value = [
        "HEADER\n", "HEADER\n", "HEADER\n",
        "CH,Amount\n",
    ]
    result = format_paypal_report(mock_sftp, "test.csv", "2025-02-02")
    assert result == "[]"


def test_format_paypal_report_no_sb_rows(mock_sftp):
    """Test formatting when no SB rows present."""
    mock_sftp.open.return_value.readlines.return_value = [
        "HEADER\n", "HEADER\n", "HEADER\n",
        "CH,Amount\n",
        "SF,0\n",
    ]
    result = format_paypal_report(mock_sftp, "test.csv", "2025-02-02")
    assert result == "[]"


def test_get_paypal_filename():
    """Test that get_paypal_filename finds the correct file."""
    mock_connection = MagicMock()
    mock_connection.listdir.return_value = [
        "DDR-20250202.01.008.CSV",
        "DDR-20250201.01.008.CSV",
        "OTHER-20250202.CSV",
    ]

    query_date = datetime.datetime(2025, 2, 2)
    filename = get_paypal_filename(query_date, "DDR", mock_connection, "/remote_path")
    assert filename == "DDR-20250202.01.008.CSV"


def test_get_paypal_filename_test_file():
    """Test that get_paypal_filename ignores test files."""
    mock_connection = MagicMock()
    mock_connection.listdir.return_value = [
        "DDR-20250202_TEST.01.008.CSV",
        "DDR-20250202.01.008.CSV",
    ]

    query_date = datetime.datetime(2025, 2, 2)
    filename = get_paypal_filename(query_date, "DDR", mock_connection, "/remote_path")
    assert filename == "DDR-20250202.01.008.CSV"


def test_get_paypal_filename_no_match():
    """Test when no matching file is found."""
    mock_connection = MagicMock()
    mock_connection.listdir.return_value = ["OTHER-20250202.CSV"]

    query_date = datetime.datetime(2025, 2, 2)
    filename = get_paypal_filename(query_date, "DDR", mock_connection, "/remote_path")
    assert filename is None


def test_get_paypal_filename_multiple_matches():
    """Test behavior when multiple matching files exist."""
    mock_connection = MagicMock()
    mock_connection.listdir.return_value = [
        "DDR-20250202.01.008.CSV",
        "DDR-20250202.02.008.CSV",
    ]

    query_date = datetime.datetime(2025, 2, 2)
    filename = get_paypal_filename(query_date, "DDR", mock_connection, "/remote_path")
    assert filename == "DDR-20250202.01.008.CSV"


@patch("edx_argoutils.paypal.list_object_keys_from_s3")
@patch("edx_argoutils.paypal.Transport")
@patch("edx_argoutils.paypal.SFTPClient.from_transport")
def test_fetch_paypal_report_existing_s3(mock_sftp, mock_transport, mock_s3):
    """Test that fetch_paypal_report skips downloading if file exists in S3."""
    mock_s3.return_value = ["existing_file.csv"]
    result = fetch_paypal_report(
        date="2025-02-02",
        paypal_credentials={},
        paypal_report_prefix="DDR",
        paypal_report_check_column_name="Amount",
        s3_bucket="test-bucket",
        s3_path="paypal-reports/",
        overwrite=False,
        host="sftp.example.com",
        port=22,
        remote_path="/reports/",
    )
    assert result is None


@patch("edx_argoutils.paypal.list_object_keys_from_s3", return_value=[])
@patch("edx_argoutils.paypal.Transport")
@patch("edx_argoutils.paypal.SFTPClient.from_transport")
def test_fetch_paypal_report_success(mock_sftp, mock_transport, mock_s3):
    """Test successful report fetch and format."""
    mock_sftp.return_value.listdir.return_value = ["DDR-20250202.01.008.CSV"]
    mock_sftp.return_value.open.return_value.readlines.return_value = [
        "HEADER\n", "HEADER\n", "HEADER\n",
        "CH,Amount\n",
        "SB,100\n",
        "SB,200\n",
        "SF,2\n",
    ]

    result = fetch_paypal_report(
        date="2025-02-02",
        paypal_credentials={"username": "test", "password": "test"},
        paypal_report_prefix="DDR",
        paypal_report_check_column_name="Amount",
        s3_bucket="test-bucket",
        s3_path="paypal-reports/",
        overwrite=True,
        host="sftp.example.com",
        port=22,
        remote_path="/reports/",
    )
    assert result is not None
    date, formatted_report = result
    assert date == "2025-02-02"
    assert formatted_report == json.dumps([
        {"CH": "SB", "Amount": "100", "report_date": "2025-02-02"},
        {"CH": "SB", "Amount": "200", "report_date": "2025-02-02"},
    ])


@patch("edx_argoutils.paypal.list_object_keys_from_s3", return_value=[])
@patch("edx_argoutils.paypal.Transport")
@patch("edx_argoutils.paypal.SFTPClient.from_transport")
def test_fetch_paypal_report_missing_file(mock_sftp, mock_transport, mock_s3):
    """Test handling of missing remote file."""
    mock_sftp.return_value.listdir.return_value = []

    with pytest.raises(RemoteFileNotFoundError, match="Remote File Not found for date: 2025-02-02"):
        fetch_paypal_report(
            date="2025-02-02",
            paypal_credentials={"username": "test", "password": "test"},
            paypal_report_prefix="DDR",
            paypal_report_check_column_name="Amount",
            s3_bucket="test-bucket",
            s3_path="paypal-reports/",
            overwrite=True,
            host="sftp.example.com",
            port=22,
            remote_path="/reports/",
        )


@patch("edx_argoutils.paypal.list_object_keys_from_s3", return_value=[])
@patch("edx_argoutils.paypal.Transport")
@patch("edx_argoutils.paypal.SFTPClient.from_transport")
def test_fetch_paypal_report_invalid_credentials(mock_sftp, mock_transport, mock_s3):
    """Test handling of invalid credentials."""
    mock_transport.return_value.connect.side_effect = Exception("Authentication failed")

    with pytest.raises(Exception, match="Authentication failed"):
        fetch_paypal_report(
            date="2025-02-02",
            paypal_credentials={"username": "invalid", "password": "invalid"},
            paypal_report_prefix="DDR",
            paypal_report_check_column_name="Amount",
            s3_bucket="test-bucket",
            s3_path="paypal-reports/",
            overwrite=True,
            host="sftp.example.com",
            port=22,
            remote_path="/reports/",
        )


@patch("edx_argoutils.paypal.list_object_keys_from_s3", return_value=[])
@patch("edx_argoutils.paypal.Transport")
@patch("edx_argoutils.paypal.SFTPClient.from_transport")
def test_fetch_paypal_report_invalid_date(mock_sftp, mock_transport, mock_s3):
    """Test handling of invalid date format."""
    with pytest.raises(ValueError):
        fetch_paypal_report(
            date="invalid-date",  # Invalid date format
            paypal_credentials={"username": "test", "password": "test"},
            paypal_report_prefix="DDR",
            paypal_report_check_column_name="Amount",
            s3_bucket="test-bucket",
            s3_path="paypal-reports/",
            overwrite=True,
            host="localhost",  # Use localhost to avoid DNS lookup
            port=22,
            remote_path="/reports/",
        )