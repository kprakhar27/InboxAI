import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
from datetime import datetime, timezone
import json

# Add the parent directory to sys.path
sys.path.append('/Users/kprakhar27/Documents/GitHub/InboxAI')

# Mock all required modules before importing the module under test
sys.modules['airflow'] = MagicMock()
sys.modules['airflow.operators'] = MagicMock()
sys.modules['airflow.operators.trigger_dagrun'] = MagicMock()
sys.modules['airflow.exceptions'] = MagicMock()
sys.modules['dotenv'] = MagicMock()
sys.modules['pydantic'] = MagicMock()
sys.modules['services'] = MagicMock()
sys.modules['services.gmail_service'] = MagicMock()
sys.modules['services.storage_service'] = MagicMock()
sys.modules['utils'] = MagicMock()
sys.modules['utils.airflow_utils'] = MagicMock()
sys.modules['utils.db_utils'] = MagicMock()

# Use function-level mocking for the actual tests
# Import the functions to be tested here
from data_pipeline.airflow.dags.tasks.email_fetch_tasks import (
    get_batch_data_from_trigger,
    process_emails_batch,
    upload_raw_data_to_gcs,
    publish_metrics_task,
    validation_task,
    trigger_preprocessing_pipeline,
    send_failure_email,
    send_success_email
)

class TestEmailFetchTasks(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        # Create common test fixtures
        self.mock_context = {
            'task_instance': MagicMock(),
            'ti': MagicMock(),
            'dag_run': MagicMock(
                conf={
                    'email_address': 'test@example.com',
                    'user_id': 'user123',
                    'message_ids': ['msg1', 'msg2', 'msg3'],
                    'batch_number': 1,
                    'total_batches': 2,
                    'start_timestamp': datetime.now(timezone.utc).isoformat(),
                    'end_timestamp': datetime.now(timezone.utc).isoformat()
                }
            )
        }
        
        # Set up current time
        self.now = datetime.now(timezone.utc)
        
    @patch('data_pipeline.airflow.dags.tasks.email_fetch_tasks.logger')
    def test_get_batch_data_from_trigger(self, mock_logger):
        """Test extracting batch data from the triggering DAG."""
        # Setup
        mock_ti = MagicMock()
        mock_context = {
            'task_instance': mock_ti,
            'ti': mock_ti,
            'dag_run': MagicMock(
                conf={
                    'email_address': 'test@example.com',
                    'user_id': 'user123',
                    'message_ids': ['msg1', 'msg2', 'msg3'],
                    'batch_number': 1,
                    'total_batches': 2,
                    'start_timestamp': '2023-01-01T00:00:00+00:00',
                    'end_timestamp': '2023-01-02T00:00:00+00:00'
                }
            )
        }
        
        # Execute the function
        result = get_batch_data_from_trigger(**mock_context)
        
        # Verify results
        self.assertEqual(result['email'], 'test@example.com')
        self.assertEqual(result['user_id'], 'user123')
        self.assertEqual(result['message_ids'], ['msg1', 'msg2', 'msg3'])
        self.assertEqual(result['batch_number'], 1)
        self.assertEqual(result['total_batches'], 2)
        mock_ti.xcom_push.assert_called_once()
    
    @patch('data_pipeline.airflow.dags.tasks.email_fetch_tasks.get_db_session')
    @patch('data_pipeline.airflow.dags.tasks.email_fetch_tasks.authenticate_gmail')
    @patch('data_pipeline.airflow.dags.tasks.email_fetch_tasks.GmailService')
    @patch('data_pipeline.airflow.dags.tasks.email_fetch_tasks.retrieve_email_data')
    @patch('data_pipeline.airflow.dags.tasks.email_fetch_tasks.validate_emails')
    @patch('data_pipeline.airflow.dags.tasks.email_fetch_tasks.save_emails')
    @patch('data_pipeline.airflow.dags.tasks.email_fetch_tasks.update_last_read_timestamp')
    @patch('data_pipeline.airflow.dags.tasks.email_fetch_tasks.generate_run_id')
    def test_process_emails_batch(self, mock_generate_run_id, mock_update_last_read_timestamp, 
                                  mock_save_emails, mock_validate_emails, mock_retrieve_email_data, 
                                  mock_gmail_service, mock_authenticate_gmail, mock_get_db_session):
        """Test processing a batch of emails."""
        # Setup
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        mock_credentials = MagicMock()
        mock_authenticate_gmail.return_value = mock_credentials
        mock_gmail = MagicMock()
        mock_gmail_service.return_value = mock_gmail
        mock_generate_run_id.return_value = "test-run-id"
        
        # Mock xcom_pull to return batch_data
        mock_ti = MagicMock()
        mock_ti.xcom_pull.return_value = {
            'email': 'test@example.com',
            'user_id': 'user123',
            'message_ids': ['msg1', 'msg2', 'msg3'],
            'batch_number': 2,  # Last batch
            'total_batches': 2,
            'start_timestamp': '2023-01-01T00:00:00+00:00',
            'end_timestamp': '2023-01-02T00:00:00+00:00'
        }
        
        mock_context = {
            'task_instance': mock_ti,
            'ti': mock_ti
        }
        
        # Mock email retrieval and validation
        mock_emails_data = [{'id': 'msg1'}, {'id': 'msg2'}, {'id': 'msg3'}]
        mock_retrieve_email_data.return_value = mock_emails_data
        mock_validate_emails.return_value = (mock_emails_data, 0)  # All emails valid
        mock_save_emails.return_value = 3  # All emails saved
        
        # Execute the function
        result = process_emails_batch(**mock_context)
        
        # Verify results
        self.assertEqual(result['emails_processed'], 3)
        self.assertEqual(result['emails_validated'], 3)
        self.assertEqual(result['validation_errors'], 0)
        mock_authenticate_gmail.assert_called_once_with(mock_session, 'test@example.com')
        mock_retrieve_email_data.assert_called_once_with(mock_gmail, ['msg1', 'msg2', 'msg3'])
        mock_validate_emails.assert_called_once_with(mock_emails_data)
        mock_save_emails.assert_called_once()
        mock_ti.xcom_push.assert_any_call(key="run_id", value="test-run-id")
        mock_update_last_read_timestamp.assert_called_once()  # Should be called for last batch

    @patch('data_pipeline.airflow.dags.tasks.email_fetch_tasks.StorageService')
    @patch('data_pipeline.airflow.dags.tasks.email_fetch_tasks.os.path.exists')
    @patch('data_pipeline.airflow.dags.tasks.email_fetch_tasks.os.getenv')
    def test_upload_raw_data_to_gcs(self, mock_getenv, mock_exists, mock_storage_service):
        """Test uploading raw data to GCS."""
        # Setup
        mock_ti = MagicMock()
        mock_ti.xcom_pull.return_value = 'test-run-id'
        
        mock_context = {
            'ti': mock_ti,
            'dag_run': MagicMock(
                conf={
                    'email_address': 'test@example.com',
                    'user_id': 'user123'
                }
            )
        }
        
        # Mock storage service
        mock_storage = MagicMock()
        mock_storage_service.return_value = mock_storage
        mock_storage.get_emails_dir.return_value = '/tmp/emails/test@example.com/test-run-id'
        mock_exists.return_value = True
        mock_getenv.return_value = 'test-bucket'
        
        # Mock upload stats
        mock_upload_stats = {'files_uploaded': 10, 'bytes_uploaded': 1024}
        mock_storage.upload_directory_to_gcs.return_value = mock_upload_stats
        
        # Execute the function
        result = upload_raw_data_to_gcs(**mock_context)
        
        # Verify results
        self.assertEqual(result, 'gs://test-bucket/raw/user123/test-run-id/test@example.com')
        mock_storage.get_emails_dir.assert_called_once_with('test@example.com', 'test-run-id', 'user123')
        mock_storage.upload_directory_to_gcs.assert_called_once()
        mock_ti.xcom_push.assert_any_call(key='gcs_uri', value='gs://test-bucket/raw/user123/test-run-id/test@example.com')
        mock_ti.xcom_push.assert_any_call(key='upload_stats', value=mock_upload_stats)

    @patch('data_pipeline.airflow.dags.tasks.email_fetch_tasks.get_db_session')
    @patch('data_pipeline.airflow.dags.tasks.email_fetch_tasks.add_preprocessing_summary')
    def test_publish_metrics_task(self, mock_add_preprocessing_summary, mock_get_db_session):
        """Test publishing metrics."""
        # Setup
        mock_ti = MagicMock()
        mock_ti.xcom_pull.side_effect = lambda key: 'test-run-id' if key == 'run_id' else {
            'total_messages_retrieved': 10,
            'emails_processed': 10,
            'emails_validated': 8,
            'validation_errors': 2
        }
        
        mock_context = {
            'ti': mock_ti,
            'dag_run': MagicMock(
                conf={'email_address': 'test@example.com'}
            )
        }
        
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        # Execute the function
        publish_metrics_task(**mock_context)
        
        # Verify results
        mock_add_preprocessing_summary.assert_called_once_with(
            mock_session, 'test-run-id', 'test@example.com', 10, 0, 8, 0, 2, 0
        )
        mock_session.close.assert_called_once()

    def test_validation_task(self):
        """Test validation task."""
        # Setup
        mock_ti = MagicMock()
        
        # Update to have fewer validation errors to pass the data_quality check
        # Now we have 10 emails with only 0 errors (0.0 error rate, which is < 0.1)
        # This ensures metrics_consistency: emails_validated(10) + validation_errors(0) == total_messages_retrieved(10)
        mock_processing_metrics = {
            'emails_validated': 10,
            'validation_errors': 0,
            'total_messages_retrieved': 10
        }
        
        # Mock upload stats with the 'successful' key that the function is looking for
        mock_upload_stats = {'successful': 1}
        
        # Configure the mock to return different values based on the key
        mock_ti.xcom_pull.side_effect = lambda key: (
            mock_processing_metrics if key == 'email_processing_metrics' 
            else mock_upload_stats
        )
        
        mock_context = {'ti': mock_ti}
        
        # Execute the function
        result = validation_task(**mock_context)
        
        # Verify results
        self.assertTrue(result)
        mock_ti.xcom_push.assert_called_once()

    @patch('data_pipeline.airflow.dags.tasks.email_fetch_tasks.TriggerDagRunOperator')
    def test_trigger_preprocessing_pipeline(self, mock_trigger_operator):
        """Test triggering preprocessing pipeline."""
        # Setup
        mock_ti = MagicMock()
        mock_ti.xcom_pull.return_value = 'gs://test-bucket/raw/user123/test-run-id/test@example.com'
        
        mock_context = {'ti': mock_ti}
        
        mock_trigger = MagicMock()
        mock_trigger_operator.return_value = mock_trigger
        
        # Execute the function
        trigger_preprocessing_pipeline(**mock_context)
        
        # Verify results
        mock_trigger_operator.assert_called_once()
        mock_trigger.execute.assert_called_once_with(context=mock_context)

    @patch('data_pipeline.airflow.dags.tasks.email_fetch_tasks.generate_email_content')
    @patch('data_pipeline.airflow.dags.tasks.email_fetch_tasks.send_notification_email')
    def test_send_failure_email(self, mock_send_email, mock_generate_content):
        """Test sending failure email."""
        # Setup
        mock_generate_content.return_value = ('Failure Subject', 'Failure Body')
        mock_send_email.return_value = True
        
        mock_ti = MagicMock()
        mock_ti.xcom_pull.return_value = 'test-run-id'
        
        mock_context = {'ti': mock_ti}
        
        # Execute the function
        result = send_failure_email(**mock_context)
        
        # Verify results
        self.assertTrue(result)
        mock_generate_content.assert_called_once_with(mock_context, type='failure')
        mock_send_email.assert_called_once_with('Failure Subject', 'Failure Body')

    @patch('data_pipeline.airflow.dags.tasks.email_fetch_tasks.generate_email_content')
    @patch('data_pipeline.airflow.dags.tasks.email_fetch_tasks.send_notification_email')
    def test_send_success_email(self, mock_send_email, mock_generate_content):
        """Test sending success email."""
        # Setup
        mock_generate_content.return_value = ('Success Subject', 'Success Body')
        mock_send_email.return_value = True
        
        mock_context = {'ti': MagicMock()}
        
        # Execute the function
        result = send_success_email(**mock_context)
        
        # Verify results
        self.assertTrue(result)
        mock_generate_content.assert_called_once_with(mock_context, type='success')
        mock_send_email.assert_called_once_with('Success Subject', 'Success Body')

if __name__ == '__main__':
    unittest.main()
