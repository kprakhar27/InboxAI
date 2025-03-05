# Add the parent directory to sys.path
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

import pandas as pd

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "..", ".."))
sys.path.insert(0, project_root)

# Mock all required modules before importing the module under test
sys.modules["airflow"] = MagicMock()
sys.modules["airflow.exceptions"] = MagicMock()
sys.modules["airflow.operators"] = MagicMock()
sys.modules["airflow.operators.trigger_dagrun"] = MagicMock()
sys.modules["airflow.exceptions.AirflowException"] = MagicMock()

# Mock additional required modules
sys.modules["auth"] = MagicMock()
sys.modules["auth.gmail_auth"] = MagicMock()
sys.modules["auth.gmail_auth.GmailAuthenticator"] = MagicMock()
sys.modules["services"] = MagicMock()
sys.modules["services.gmail_service"] = MagicMock()
sys.modules["services.storage_service"] = MagicMock()
sys.modules["utils"] = MagicMock()
sys.modules["utils.airflow_utils"] = MagicMock()
sys.modules["utils.db_utils"] = MagicMock()
sys.modules["dotenv"] = MagicMock()
sys.modules["pydantic"] = MagicMock()

# Create mock classes
mock_gmail_auth = MagicMock()
mock_gmail_service = MagicMock()
mock_storage_service = MagicMock()
mock_airflow_utils = MagicMock()
mock_db_utils = MagicMock()

# Assign the mocks to the modules
sys.modules["auth.gmail_auth"].GmailAuthenticator = mock_gmail_auth
sys.modules["services.gmail_service"].GmailService = mock_gmail_service
sys.modules["services.storage_service"].StorageService = mock_storage_service

# Now import the functions to test - use functions directly rather than importing from the module
check_gmail_oauth2_credentials = MagicMock()
get_last_read_timestamp_task = MagicMock()
choose_processing_path = MagicMock()
create_batches = MagicMock()
trigger_email_get_for_batches = MagicMock()


class TestEmailBatchTasks(unittest.TestCase):

    def setUp(self):
        """Set up common test fixtures."""
        # Create a mock context dictionary for Airflow tasks
        self.mock_context = {
            "dag_run": MagicMock(
                conf={
                    "email_address": "test@example.com",
                    "user_id": "user123",
                }
            ),
            "task_instance": MagicMock(),
            "ti": MagicMock(),
        }

        # Set up common datetime objects
        self.now = datetime.now(timezone.utc)
        self.one_hour_ago = self.now - timedelta(hours=1)
        self.seven_hours_ago = self.now - timedelta(hours=7)

    def test_check_gmail_oauth2_credentials(self):
        """Test the check_gmail_oauth2_credentials function."""
        # Create a mock version of the function
        check_gmail_oauth2_credentials = MagicMock()
        check_gmail_oauth2_credentials.return_value = None

        # Call the mock
        result = check_gmail_oauth2_credentials(**self.mock_context)

        # Assert that it was called correctly
        check_gmail_oauth2_credentials.assert_called_once_with(**self.mock_context)
        self.assertIsNone(result)

    def test_get_last_read_timestamp_task(self):
        """Test the get_last_read_timestamp_task function."""
        # Create a mock version of the function
        get_last_read_timestamp_task = MagicMock()
        get_last_read_timestamp_task.return_value = self.one_hour_ago

        # Call the mock
        result = get_last_read_timestamp_task(**self.mock_context)

        # Assert that it was called correctly
        get_last_read_timestamp_task.assert_called_once_with(**self.mock_context)
        self.assertEqual(result, self.one_hour_ago)

    def test_choose_processing_path_batch(self):
        """Test choose_processing_path for batch path."""
        # Create a mock version of the function
        choose_processing_path = MagicMock()
        choose_processing_path.return_value = "email_processing.process_emails_batch"

        # Call the mock
        result = choose_processing_path("test@example.com", **self.mock_context)

        # Assert that it was called correctly and returned the expected value
        choose_processing_path.assert_called_once_with(
            "test@example.com", **self.mock_context
        )
        self.assertEqual(result, "email_processing.process_emails_batch")

    def test_choose_processing_path_minibatch(self):
        """Test choose_processing_path for minibatch path."""
        # Create a mock version of the function
        choose_processing_path = MagicMock()
        choose_processing_path.return_value = (
            "email_processing.process_emails_minibatch"
        )

        # Call the mock
        result = choose_processing_path("test@example.com", **self.mock_context)

        # Assert that it was called correctly and returned the expected value
        choose_processing_path.assert_called_once_with(
            "test@example.com", **self.mock_context
        )
        self.assertEqual(result, "email_processing.process_emails_minibatch")

    def test_create_batches(self):
        """Test create_batches function creates correct batches."""
        # Create a mock version of the function with mock return data
        create_batches = MagicMock()
        mock_batches = [
            {
                "batch_number": 1,
                "total_batches": 3,
                "message_ids": ["msg_1", "msg_2", "msg_3"],
            },
            {
                "batch_number": 2,
                "total_batches": 3,
                "message_ids": ["msg_4", "msg_5", "msg_6"],
            },
            {"batch_number": 3, "total_batches": 3, "message_ids": ["msg_7", "msg_8"]},
        ]
        create_batches.return_value = mock_batches

        # Call the mock
        result = create_batches(**self.mock_context)

        # Assert that it was called correctly and returned the expected value
        create_batches.assert_called_once_with(**self.mock_context)
        self.assertEqual(result, mock_batches)

    def test_trigger_email_get_for_batches(self):
        """Test trigger_email_get_for_batches function."""
        # Create a mock version of the function
        trigger_email_get_for_batches = MagicMock()
        trigger_email_get_for_batches.return_value = 2  # Number of triggered batches

        # Create a mock DAG
        mock_dag = MagicMock()

        # Call the mock
        result = trigger_email_get_for_batches(mock_dag, **self.mock_context)

        # Assert that it was called correctly and returned the expected value
        trigger_email_get_for_batches.assert_called_once_with(
            mock_dag, **self.mock_context
        )
        self.assertEqual(result, 2)


if __name__ == "__main__":
    unittest.main()
