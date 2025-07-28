import mock
import pytest
import mysql.connector

from edx_argoutils import mysql as utils_mysql


@pytest.fixture
def mock_mysql_connection(mocker):  # noqa: F811
    mocker.patch.object(utils_mysql, 'create_mysql_connection')
    mock_cursor = mocker.Mock()
    mock_connection = mocker.Mock()
    mock_connection.cursor.return_value = mock_cursor
    utils_mysql.create_mysql_connection.return_value = mock_connection
    return mock_connection


def test_create_mysql_connection_success():
    credentials = {
        'username': 'test_user',
        'password': 'test_pass',
        'host': 'test_host'
    }
    with mock.patch('mysql.connector.connect') as mock_connect:
        utils_mysql.create_mysql_connection(credentials, 'test_db')
        mock_connect.assert_called_once_with(
            user='test_user',
            password='test_pass',
            host='test_host',
            database='test_db',
            autocommit=False
        )


def test_create_mysql_connection_unknown_database():
    credentials = {
        'username': 'test_user',
        'password': 'test_pass',
        'host': 'test_host'
    }
    mock_cursor = mock.Mock()
    
    with mock.patch('mysql.connector.connect') as mock_connect:
        mock_connect.side_effect = [
            mysql.connector.errors.ProgrammingError('Unknown database'),
            mock.DEFAULT
        ]
        mock_connect.return_value.cursor.return_value = mock_cursor
        
        utils_mysql.create_mysql_connection(credentials, 'test_db')
        
        assert mock_cursor.execute.call_count == 2
        mock_cursor.execute.assert_has_calls([
            mock.call('CREATE DATABASE IF NOT EXISTS test_db'),
            mock.call('USE test_db')
        ])


def test_load_s3_data_to_mysql_no_overwrite_existing_data(mock_mysql_connection):
    mock_cursor = mock_mysql_connection.cursor()
    mock_cursor.fetchone.return_value = [1]

    utils_mysql.load_s3_data_to_mysql(
        aurora_credentials={},
        database="test_database",
        table="test_table",
        table_columns=[('id', 'int'), ('course_id', 'varchar(255) NOT NULL')],
        s3_url="s3://edx-test/test/",
        overwrite=False
    )


def test_load_s3_data_to_mysql_overwrite_without_record_filter(mock_mysql_connection):
    mock_cursor = mock_mysql_connection.cursor()
    mock_cursor.fetchone.return_value = [1]

    utils_mysql.load_s3_data_to_mysql(
        aurora_credentials={},
        database="test_database",
        table="test_table",
        table_columns=[('id', 'int'), ('course_id', 'varchar(255) NOT NULL')],
        s3_url="s3://edx-test/test/",
        overwrite=True
    )

    mock_cursor.execute.assert_has_calls([
        mock.call("SELECT 1 FROM test_table  LIMIT 1"),
        mock.call("DELETE FROM test_table ")
    ])


def test_load_s3_data_to_mysql_overwrite_with_record_filter(mock_mysql_connection):
    mock_cursor = mock_mysql_connection.cursor()
    mock_cursor.fetchone.return_value = [1]

    utils_mysql.load_s3_data_to_mysql(
        aurora_credentials={},
        database="test_database",
        table="test_table",
        table_columns=[('id', 'int'), ('course_id', 'varchar(255) NOT NULL')],
        s3_url="s3://edx-test/test/",
        record_filter="where course_id='edX/Open_DemoX/edx_demo_course'",
        overwrite=True
    )

    mock_cursor.execute.assert_has_calls([
        mock.call("SELECT 1 FROM test_table where course_id='edX/Open_DemoX/edx_demo_course' LIMIT 1"),
        mock.call("DELETE FROM test_table where course_id='edX/Open_DemoX/edx_demo_course'")
    ])


def test_load_s3_data_to_mysql(mock_mysql_connection):
    mock_cursor = mock_mysql_connection.cursor()
    mock_cursor.fetchone.return_value = [1]

    utils_mysql.load_s3_data_to_mysql(
        aurora_credentials={},
        database="test_database",
        table="test_table",
        table_columns=[('id', 'int'), ('course_id', 'varchar(255) NOT NULL')],
        s3_url="s3://edx-test/test/",
        record_filter="where course_id='edX/Open_DemoX/edx_demo_course'",
        ignore_num_lines=2,
        overwrite=True
    )

    mock_cursor.execute.assert_has_calls([
        mock.call("\n        CREATE TABLE IF NOT EXISTS test_table (id int,course_id varchar(255) NOT NULL)\n    "),
        mock.call("SELECT 1 FROM test_table where course_id='edX/Open_DemoX/edx_demo_course' LIMIT 1"),
        mock.call("DELETE FROM test_table where course_id='edX/Open_DemoX/edx_demo_course'"),
        mock.call("\n            LOAD DATA FROM S3 PREFIX 's3://edx-test/test/'\n            INTO TABLE test_table\n            FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY ''\n            ESCAPED BY '\\\\'\n            IGNORE 2 LINES\n        ")
    ])


def test_load_s3_data_to_mysql_overwrite_with_temp_table(mock_mysql_connection):
    mock_cursor = mock_mysql_connection.cursor()
    mock_cursor.fetchone.return_value = [1]

    utils_mysql.load_s3_data_to_mysql(
        aurora_credentials={},
        database="test_database",
        table="test_table",
        table_columns=[('id', 'int'), ('course_id', 'varchar(255) NOT NULL')],
        s3_url="s3://edx-test/test/",
        overwrite=True,
        overwrite_with_temp_table=True,
    )

    mock_cursor.execute.assert_has_calls([
        mock.call("\n        CREATE TABLE IF NOT EXISTS test_table (id int,course_id varchar(255) NOT NULL)\n    "),
        mock.call("SELECT 1 FROM test_table  LIMIT 1"),
        mock.call("DROP TABLE IF EXISTS test_table_old"),
        mock.call("DROP TABLE IF EXISTS test_table_temp"),
        mock.call("CREATE TABLE test_table_temp (id int,course_id varchar(255) NOT NULL)"),
        mock.call("\n            LOAD DATA FROM S3 PREFIX 's3://edx-test/test/'\n            INTO TABLE test_table_temp\n            FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY ''\n            ESCAPED BY '\\\\'\n            IGNORE 0 LINES\n        "),
        mock.call("RENAME TABLE test_table to test_table_old, test_table_temp to test_table"),
        mock.call("DROP TABLE IF EXISTS test_table_old"),
        mock.call("DROP TABLE IF EXISTS test_table_temp")
    ])


def test_table_creation_with_indexes(mock_mysql_connection):
    mock_cursor = mock_mysql_connection.cursor()
    mock_cursor.fetchone.return_value = None

    utils_mysql.load_s3_data_to_mysql(
        aurora_credentials={},
        database="test_database",
        table="test_table",
        table_columns=[('user_id', 'int'), ('course_id', 'varchar(255) NOT NULL')],
        table_indexes=[('user_id',), ('course_id',), ('user_id', 'course_id')],
        s3_url="s3://edx-test/test/",
        overwrite=True,
        overwrite_with_temp_table=True,
    )

    mock_cursor.execute.assert_has_calls([
        mock.call("\n        CREATE TABLE IF NOT EXISTS test_table (user_id int,course_id varchar(255) NOT NULL,INDEX (user_id),INDEX (course_id),INDEX (user_id,course_id))\n    ")
    ])


def test_load_s3_data_to_mysql_with_manifest(mock_mysql_connection):
    mock_cursor = mock_mysql_connection.cursor()
    mock_cursor.fetchone.return_value = None

    utils_mysql.load_s3_data_to_mysql(
        aurora_credentials={},
        database="test_database",
        table="test_table",
        table_columns=[('id', 'int'), ('course_id', 'varchar(255) NOT NULL')],
        s3_url="s3://edx-test/some/prefix/",
        overwrite=True,
        overwrite_with_temp_table=True,
        use_manifest=True,
    )

    mock_cursor.execute.assert_has_calls([
        mock.call("\n            LOAD DATA FROM S3 MANIFEST 's3://edx-test/some/prefix/manifest.json'\n            INTO TABLE test_table_temp\n            FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY ''\n            ESCAPED BY '\\\\'\n            IGNORE 0 LINES\n        ")
    ])


# Additional edge cases and negative tests
def test_load_s3_data_to_mysql_connection_error(mock_mysql_connection):
    mock_mysql_connection.cursor.side_effect = mysql.connector.Error("Connection error")
    
    with pytest.raises(mysql.connector.Error):
        utils_mysql.load_s3_data_to_mysql(
            aurora_credentials={},
            database="test_database",
            table="test_table",
            table_columns=[('id', 'int')],
            s3_url="s3://edx-test/test/"
        )


def test_load_s3_data_to_mysql_invalid_column_definition(mock_mysql_connection):
    mock_cursor = mock_mysql_connection.cursor()
    mock_cursor.execute.side_effect = mysql.connector.errors.ProgrammingError(
        "Invalid column definition"
    )

    with pytest.raises(mysql.connector.errors.ProgrammingError):
        utils_mysql.load_s3_data_to_mysql(
            aurora_credentials={},
            database="test_database",
            table="test_table",
            table_columns=[('id', 'INVALID_TYPE')],
            s3_url="s3://edx-test/test/"
        )


def test_load_s3_data_to_mysql_empty_credentials():
    with pytest.raises(KeyError):
        utils_mysql.load_s3_data_to_mysql(
            aurora_credentials={},
            database="test_database",
            table="test_table",
            table_columns=[('id', 'int')],
            s3_url="s3://edx-test/test/"
        )


def test_load_s3_data_to_mysql_empty_table_columns(mock_mysql_connection):
    with pytest.raises(ValueError, match="table_columns cannot be empty"):
        utils_mysql.load_s3_data_to_mysql(
            aurora_credentials={'username': 'test', 'password': 'test', 'host': 'test'},
            database="test_database",
            table="test_table",
            table_columns=[],
            s3_url="s3://edx-test/test/"
        )