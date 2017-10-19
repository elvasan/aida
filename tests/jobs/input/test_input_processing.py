import pytest
from jobs.input.input_processing import transform_input_csv, build_input_csv_file_name, input_csv_schema, \
    input_csv_transformed_schema, load_csv_file, process_input_file
from shared.utilities import ENV_LOCAL, ENV_DEV, ENV_PROD, ENV_QA, ENV_STAGING, ID_TYPE_LEAD_ID
from unittest import mock
from pyspark.sql.utils import AnalysisException
import py4j

# define mark (need followup if need this)
spark_session_enabled = pytest.mark.usefixtures("spark_session")


def test_build_input_csv_file_name_returns_correct_dev_env_name():
    full_name = build_input_csv_file_name(ENV_DEV, "us-east-1", "beestest")
    assert full_name == 'S3://jornaya-dev-us-east-1-aida-insights/beestest/input/beestest.csv'


def test_build_input_csv_file_name_returns_correct_qa_env_name():
    full_name = build_input_csv_file_name(ENV_QA, "us-east-1", "beestest")
    assert full_name == 'S3://jornaya-qa-us-east-1-aida-insights/beestest/input/beestest.csv'


def test_build_input_csv_file_name_returns_correct_staging_env_name():
    full_name = build_input_csv_file_name(ENV_STAGING, "us-east-1", "beestest")
    assert full_name == 'S3://jornaya-staging-us-east-1-aida-insights/beestest/input/beestest.csv'


def test_build_input_csv_file_name_returns_correct_prod_env_name():
    full_name = build_input_csv_file_name(ENV_PROD, "us-east-1", "beestest")
    assert full_name == 'S3://jornaya-prod-us-east-1-aida-insights/beestest/input/beestest.csv'


def test_build_input_csv_file_name_returns_local_env_name_as_samples_directory():
    full_name = build_input_csv_file_name(ENV_LOCAL, "us-east-1", "beestest")
    assert full_name == '../samples/beestest/input/beestest.csv'


def test_transform_input_csv_returns_leadid_as_input_id_and_other_columns(spark_session):
    # record_id, phone_1, phone_2, phone_3, email_1, email_2, email_3, lead_1, lead_2, lead_3, as_of_time
    raw_hash_rows = [
        (1, '', '', '', '', '', '', 'LLAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA', '', '', '1506844800'),
        (2, '', '', '', '', '', '', 'LLBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB', '', '', '1506844800')]
    input_csv_data_frame = spark_session.createDataFrame(raw_hash_rows, input_csv_schema())
    result_data_frame = transform_input_csv(input_csv_data_frame)
    extracted_row_values = [[i.record_id, i.input_id, i.input_id_type, i.as_of_time, i.has_error, i.error_message] for i
                            in result_data_frame.select(
            result_data_frame.record_id, result_data_frame.input_id, result_data_frame.input_id_type,
            result_data_frame.as_of_time, result_data_frame.has_error, result_data_frame.error_message).collect()]
    expected_rows = [
        [1, 'LLAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA', ID_TYPE_LEAD_ID, '1506844800', False, None],
        [2, 'LLBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB', ID_TYPE_LEAD_ID, '1506844800', False, None]
    ]
    assert extracted_row_values == expected_rows


def test_transform_input_csv_returns_empty_data_frame_when_no_data_present(spark_session):
    input_csv_data_frame = spark_session.createDataFrame([], input_csv_schema())
    result_data_frame = transform_input_csv(input_csv_data_frame)
    extracted_row_values = [[i.record_id, i.input_id, i.input_id_type, i.as_of_time] for i in result_data_frame.select(
        result_data_frame.record_id, result_data_frame.input_id, result_data_frame.input_id_type,
        result_data_frame.as_of_time).collect()]
    assert extracted_row_values == []


def test_transform_input_csv_returns_proper_data_frame_schema_columns(spark_session):
    input_csv_data_frame = spark_session.createDataFrame([], input_csv_schema())
    result_data_frame = transform_input_csv(input_csv_data_frame)
    assert sorted(result_data_frame.schema.names) == sorted(input_csv_transformed_schema().names)


def test_load_csv_file_loads_file(spark_session, tmpdir):
    csv_file = tmpdir.mkdir('data').join('beestest.csv')
    csv_text = "recordid,phone01,phone02,phone03,email01,email02,email03,leadid01,leadid02,leadid03,asof\r" \
               "1,,,,,,,LLAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA,,,\r" \
               "2,,,,,,,LLBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB,,,\r"
    csv_file.write(csv_text)
    loaded_df = load_csv_file(spark_session, csv_file.strpath)
    assert loaded_df.count() == 2


def test_process_input_file_end_to_end(spark_session, tmpdir, monkeypatch):
    csv_file = tmpdir.mkdir('data').join('beestest.csv')
    csv_text = "recordid,phone01,phone02,phone03,email01,email02,email03,leadid01,leadid02,leadid03,asof\r" \
               "1,,,,,,,LLAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA,,,\r" \
               "2,,,,,,,LLBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB,,,\r"
    csv_file.write(csv_text)
    mock_logger = mock.Mock()

    # mock csv file name function to return local unit test csv file from tmp directory
    monkeypatch.setattr("jobs.input.input_processing.build_input_csv_file_name", lambda x, y, z: csv_file.strpath)
    result_df = process_input_file(spark_session, mock_logger, "beestest", "unit_test", "us-east-1")
    extracted_row_values = [[i.record_id, i.input_id, i.input_id_type, i.as_of_time, i.has_error, i.error_message] for i
                            in result_df.select(
            result_df.record_id, result_df.input_id, result_df.input_id_type,
            result_df.as_of_time, result_df.has_error, result_df.error_message).collect()]
    expected_rows = [
        [1, 'LLAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA', ID_TYPE_LEAD_ID, None, False, None],
        [2, 'LLBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB', ID_TYPE_LEAD_ID, None, False, None] ]
    assert extracted_row_values == expected_rows


def test_process_input_file_throws_analysis_exception_with_missing_input_file(spark_session, tmpdir, monkeypatch):
    mock_logger = mock.Mock()
    # mock csv file name function to return invalid path
    monkeypatch.setattr("jobs.input.input_processing.build_input_csv_file_name", lambda x, y, z: "invalid_file_name")
    with pytest.raises(AnalysisException):
        process_input_file(spark_session, mock_logger, "beestest", "unit_test", "us-east-1")


def test_process_input_file_with_invalid_csv_file_format_throws_java_error(spark_session, tmpdir, monkeypatch):
    csv_file = tmpdir.mkdir('data').join('beestest.csv')
    csv_text = "wrong,header,values\r" \
               "hello,world,testing\r"
    csv_file.write(csv_text)
    mock_logger = mock.Mock()
    # mock csv file name function to return local unit test csv file from tmp directory
    monkeypatch.setattr("jobs.input.input_processing.build_input_csv_file_name", lambda x, y, z: csv_file.strpath)
    with pytest.raises(py4j.protocol.Py4JJavaError):
        result_df = process_input_file(spark_session, mock_logger, "beestest", "unit_test", "us-east-1")
        result_df.collect()

