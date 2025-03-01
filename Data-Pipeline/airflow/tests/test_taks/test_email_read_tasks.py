from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from tasks.email_read_tasks import (
    check_gmail_oauth2_credentials,
    choose_processing_path,
    get_last_read_timestamp_task,
    process_emails_batch,
    process_emails_minibatch,
)


class TestEmailReadTasks:

    @patch("tasks.email_read_tasks.GmailAuthenticator")
    def test_check_gmail_oauth2_credentials(
        self, mock_authenticator, mock_context, mock_db_session
    ):
        """Test Gmail OAuth credentials check"""
        # Setup
        mock_context["task_instance"].xcom_pull.side_effect = [
            "test@example.com",  # email
            mock_db_session,  # session
        ]
        mock_auth_instance = mock_authenticator.return_value
        mock_auth_instance.authenticate.return_value = "mock_credentials"

        # Execute
        result = check_gmail_oauth2_credentials(**mock_context)

        # Assert
        assert result == "mock_credentials"
        mock_authenticator.assert_called_once()
        mock_auth_instance.authenticate.assert_called_once()
        mock_context["task_instance"].xcom_push.assert_called_with(
            key="gmail_credentials", value="mock_credentials"
        )

    @patch("tasks.email_read_tasks.get_last_read_timestamp")
    def test_get_last_read_timestamp_task(
        self, mock_get_timestamp, mock_context, mock_db_session
    ):
        """Test getting last read timestamp"""
        # Setup
        mock_context["task_instance"].xcom_pull.side_effect = [
            mock_db_session,  # session
            "test@example.com",  # email
        ]
        last_read = datetime.now(timezone.utc) - timedelta(days=1)
        mock_get_timestamp.return_value = last_read

        # Execute
        result = get_last_read_timestamp_task(**mock_context)

        # Assert
        assert result == last_read
        mock_get_timestamp.assert_called_once()
        assert mock_context["task_instance"].xcom_push.call_count == 2

    def test_choose_processing_path_batch(self, mock_context):
        """Test choosing batch processing path for large time gap"""
        # Setup
        last_read = datetime.now(timezone.utc) - timedelta(days=40)
        end_timestamp = datetime.now(timezone.utc)
        mock_context["task_instance"].xcom_pull.side_effect = [last_read, end_timestamp]

        # Execute
        result = choose_processing_path(**mock_context)

        # Assert
        assert result == "process_emails_batch"

    def test_choose_processing_path_minibatch(self, mock_context):
        """Test choosing minibatch processing path for small time gap"""
        # Setup
        last_read = datetime.now(timezone.utc) - timedelta(days=5)
        end_timestamp = datetime.now(timezone.utc)
        mock_context["task_instance"].xcom_pull.side_effect = [last_read, end_timestamp]

        # Execute
        result = choose_processing_path(**mock_context)

        # Assert
        assert result == "process_emails_minibatch"

    @patch("tasks.email_read_tasks.GmailService")
    @patch("tasks.email_read_tasks.batch_process_emails")
    def test_process_emails_batch(
        self, mock_batch_process, mock_gmail_service, mock_context, mock_db_session
    ):
        """Test batch email processing"""
        # Setup
        mock_context["task_instance"].xcom_pull.side_effect = [
            "test@example.com",  # email
            "mock_credentials",  # gmail_credentials
            mock_db_session,  # session
            datetime(2023, 1, 1, tzinfo=timezone.utc),  # start_timestamp
            datetime(2023, 2, 1, tzinfo=timezone.utc),  # end_timestamp
        ]
        mock_service_instance = mock_gmail_service.return_value
        mock_batch_process.return_value = 25  # Number of emails processed

        # Execute
        result = process_emails_batch(**mock_context)

        # Assert
        assert result == 25
        mock_gmail_service.assert_called_once_with("mock_credentials")
        mock_batch_process.assert_called_once()
        mock_context["task_instance"].xcom_push.assert_called_with(
            key="emails_processed_count", value=25
        )

    @patch("tasks.email_read_tasks.GmailService")
    @patch("tasks.email_read_tasks.minibatch_process_emails")
    def test_process_emails_minibatch(
        self, mock_minibatch_process, mock_gmail_service, mock_context, mock_db_session
    ):
        """Test minibatch email processing"""
        # Setup
        mock_context["task_instance"].xcom_pull.side_effect = [
            "test@example.com",  # email
            "mock_credentials",  # gmail_credentials
            mock_db_session,  # session
            datetime(2023, 2, 1, tzinfo=timezone.utc),  # start_timestamp
            datetime(2023, 2, 7, tzinfo=timezone.utc),  # end_timestamp
        ]
        mock_service_instance = mock_gmail_service.return_value
        mock_minibatch_process.return_value = 15  # Number of emails processed

        # Execute
        result = process_emails_minibatch(**mock_context)

        # Assert
        assert result == 15
        mock_gmail_service.assert_called_once_with("mock_credentials")
        mock_minibatch_process.assert_called_once()
        mock_context["task_instance"].xcom_push.assert_called_with(
            key="emails_processed_count", value=15
        )
