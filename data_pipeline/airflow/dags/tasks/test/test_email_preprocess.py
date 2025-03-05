import os
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock, mock_open, patch

import pandas as pd

# Add the parent directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "..", ".."))
sys.path.insert(0, project_root)

# Mock all required modules before importing the module under test
sys.modules["airflow"] = MagicMock()
sys.modules["airflow.operators"] = MagicMock()
sys.modules["airflow.operators.trigger_dagrun"] = MagicMock()
sys.modules["airflow.exceptions"] = MagicMock()
sys.modules["airflow.models"] = MagicMock()
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.storage"] = MagicMock()
sys.modules["services"] = MagicMock()
sys.modules["services.storage_service"] = MagicMock()
sys.modules["utils"] = MagicMock()
sys.modules["utils.airflow_utils"] = MagicMock()
sys.modules["utils.preprocessing_utils"] = MagicMock()

# Import the functions to be tested
from data_pipeline.airflow.dags.tasks.email_preprocess_tasks import (
    download_raw_from_gcs,
    preprocess_emails,
    trigger_embedding_pipeline,
    upload_processed_to_gcs,
)


class TestEmailPreprocessTasks(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        # Create common test fixtures
        self.mock_context = {
            "ti": MagicMock(),
            "ds": "2023-01-01",
            "dag_run": MagicMock(
                conf={
                    "gcs_uri": "gs://test-bucket/raw/user123/test-run-id/test@example.com"
                }
            ),
        }

        # Create a temporary directory path
        self.tmp_dir = "/tmp/email_preprocessing"

    @patch("data_pipeline.airflow.dags.tasks.email_preprocess_tasks.storage.Client")
    @patch(
        "data_pipeline.airflow.dags.tasks.email_preprocess_tasks.os.makedirs",
        return_value=None,
    )
    def test_download_raw_from_gcs(self, mock_makedirs, mock_storage_client):
        """Test downloading raw data from GCS."""
        # Setup
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # Execute the function
        result = download_raw_from_gcs(**self.mock_context)

        # Verify results
        expected_path = f"{self.tmp_dir}/raw_emails_2023-01-01.parquet"
        self.assertEqual(result, expected_path)
        mock_storage_client.return_value.bucket.assert_called_once()
        mock_bucket.blob.assert_called_once()
        mock_blob.download_to_filename.assert_called_once()
        self.mock_context["ti"].xcom_push.assert_called_once_with(
            key="local_file_path", value=expected_path
        )

    @patch("data_pipeline.airflow.dags.tasks.email_preprocess_tasks.EmailPreprocessor")
    @patch("data_pipeline.airflow.dags.tasks.email_preprocess_tasks.os.makedirs")
    def test_preprocess_emails(self, mock_makedirs, mock_email_preprocessor_class):
        """Test preprocessing email data."""
        # Create mock preprocessor instance
        mock_preprocessor = MagicMock()
        mock_email_preprocessor_class.return_value = mock_preprocessor

        # Create a test DataFrame that would be returned by load_data
        raw_df = pd.DataFrame(
            {
                "plain_text": ["text1", "text2"],
                "html": ["html1", "html2"],
                "message_id": ["id1", "id2"],
                "from_email": ["from1", "from2"],
                "subject": ["subject1", "subject2"],
            }
        )

        # Create processed DataFrame that would be returned by preprocess
        processed_df = pd.DataFrame(
            {
                "plain_text": ["text1", "text2"],
                "html": ["html1", "html2"],
                "plain_text_decoded": ["decoded1", "decoded2"],
                "html_decoded": ["decoded_html1", "decoded_html2"],
                "redacted_text": ["redacted1", "redacted2"],
                "message_id": ["id1", "id2"],
                "from_email": ["from1", "from2"],
                "subject": ["subject1", "subject2"],
                "date": ["2023-01-01", "2023-01-02"],
                "labels": ["label1", "label2"],
            }
        )

        # Set up the mocks to return our test data
        mock_preprocessor.load_data.return_value = raw_df
        mock_preprocessor.preprocess.return_value = processed_df

        # Mock the Series.apply method to avoid the original implementation
        with patch(
            "pandas.Series.apply", return_value=pd.Series(["decoded1", "decoded2"])
        ):
            # Mock context
            mock_context = {
                "ti": MagicMock(),
                "ds": "2023-01-01",
                "dag_run": MagicMock(
                    conf={"gcs_uri": "gs://test-bucket/raw/test-user/test"}
                ),
            }

            # Execute the function
            result = preprocess_emails(**mock_context)

        # Verify results
        self.assertTrue(result)
        mock_preprocessor.load_data.assert_called_once()
        mock_preprocessor.preprocess.assert_called_once()

        # Check if xcom_push was called with specific args
        # Get all calls to xcom_push
        calls = mock_context["ti"].xcom_push.call_args_list
        expected_call_found = False

        for call in calls:
            args, kwargs = call
            if "key" in kwargs and kwargs["key"] == "preprocessing_metadata":
                if (
                    "value" in kwargs
                    and kwargs["value"].get("execution_date") == "2023-01-01"
                ):
                    expected_call_found = True
                    break

        self.assertTrue(
            expected_call_found,
            "Expected xcom_push call with preprocessing_metadata not found",
        )

    @patch("data_pipeline.airflow.dags.tasks.email_preprocess_tasks.storage.Client")
    @patch("data_pipeline.airflow.dags.tasks.email_preprocess_tasks.pd.read_parquet")
    def test_upload_processed_to_gcs(self, mock_read_parquet, mock_storage_client):
        """Test uploading processed data to GCS."""
        # Setup mock DataFrame
        mock_df = pd.DataFrame(
            {"message_id": ["id1", "id2"], "from_email": ["from1", "from2"]}
        )
        mock_read_parquet.return_value = mock_df

        # Setup storage mocks
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # Mock context with properly aligned ti and task_instance references
        ti = MagicMock()
        mock_context = {
            "ti": ti,
            "task_instance": ti,  # Use the same MagicMock for both keys
            "ds": "2023-01-01",
            "dag_run": MagicMock(
                conf={
                    "gcs_uri": "gs://test-bucket/raw/user123/test-run-id/test@example.com"
                }
            ),
        }

        # Mock ti.xcom_pull to return the expected path
        mock_context["ti"].xcom_pull.return_value = "/tmp/preprocessed/emails.parquet"

        # Execute the function with the patched environment
        result = upload_processed_to_gcs(**mock_context)

        # Verify results
        self.assertTrue(result.startswith("gs://"))
        mock_storage_client.return_value.bucket.assert_called_once()
        mock_bucket.blob.assert_called_once()
        mock_blob.upload_from_filename.assert_called_once()
        ti.xcom_push.assert_called_with(key="processed_gcs_uri", value=result)

    @patch(
        "data_pipeline.airflow.dags.tasks.email_preprocess_tasks.TriggerDagRunOperator"
    )
    def test_trigger_embedding_pipeline(self, mock_trigger_operator):
        """Test triggering the embedding pipeline."""
        # Setup
        mock_trigger = MagicMock()
        mock_trigger_operator.return_value = mock_trigger

        # Mock context
        mock_ti = MagicMock()
        mock_ti.xcom_pull.return_value = (
            "gs://test-bucket/processed/user123/test-run-id/test@example.com"
        )
        mock_context = {"task_instance": mock_ti, "ti": mock_ti, "ds": "2023-01-01"}

        # Execute the function
        result = trigger_embedding_pipeline(**mock_context)

        # Verify results
        self.assertTrue(result)
        mock_trigger_operator.assert_called_once()
        mock_trigger.execute.assert_called_once()

        # Verify the configuration passed to the triggered DAG
        trigger_call_args = mock_trigger_operator.call_args[1]
        self.assertEqual(
            trigger_call_args["trigger_dag_id"], "email_embedding_generation_pipeline"
        )
        self.assertTrue("execution_date" in trigger_call_args["conf"])
        self.assertTrue("processed_gcs_uri" in trigger_call_args["conf"])


if __name__ == "__main__":
    unittest.main()
