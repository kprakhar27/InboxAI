import unittest
import os
import sys
from unittest import mock

# Add project root to Python path 
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Mock all required imported modules to avoid dependency issues
mocks = {
    'utils.gcp_logging_utils': mock.MagicMock(),
    'tasks.email_fetch_tasks': mock.MagicMock(),
    'utils.airflow_utils': mock.MagicMock(),
}

# Set up the mocks
for module_name, mock_obj in mocks.items():
    sys.modules[module_name] = mock_obj

# Create specific function mocks needed by the DAG file
sys.modules['utils.gcp_logging_utils'].setup_gcp_logging = mock.MagicMock()
sys.modules['utils.gcp_logging_utils'].setup_gcp_logging.return_value = mock.MagicMock()
sys.modules['tasks.email_fetch_tasks'].get_batch_data_from_trigger = mock.MagicMock()
sys.modules['tasks.email_fetch_tasks'].process_emails_batch = mock.MagicMock()
sys.modules['tasks.email_fetch_tasks'].publish_metrics_task = mock.MagicMock()
sys.modules['tasks.email_fetch_tasks'].send_failure_email = mock.MagicMock()
sys.modules['tasks.email_fetch_tasks'].trigger_preprocessing_pipeline = mock.MagicMock()
sys.modules['tasks.email_fetch_tasks'].upload_raw_data_to_gcs = mock.MagicMock()
sys.modules['tasks.email_fetch_tasks'].validation_task = mock.MagicMock()
sys.modules['utils.airflow_utils'].failure_callback = mock.MagicMock()

# Import Airflow modules and the DAG file
from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator

# Import the actual DAG file
from email_02_fetch_pipeline import dag

class TestEmailFetchPipeline(unittest.TestCase):
    """Test for email_fetch_pipeline DAG"""
    
    def test_dag_id(self):
        """Test that the DAG ID is correct"""
        self.assertEqual(dag.dag_id, "email_fetch_pipeline")
        
    def test_dag_default_args(self):
        """Test that the DAG has the expected default arguments"""
        self.assertEqual(dag.default_args["owner"], "airflow")
        self.assertEqual(dag.default_args["retries"], 3)
        self.assertTrue("on_failure_callback" in dag.default_args)
        
    def test_task_structure(self):
        """Test the structure of tasks in the DAG"""
        # Define the expected tasks
        expected_tasks = [
            "start",
            "get_batch_data",
            "process_emails_batch",
            "upload_raw_to_gcs",
            "publish_metrics",
            "validation_task",
            "trigger_preprocessing_pipeline",
            "send_failure_email"
        ]
        
        # Check that all expected tasks exist
        for task_id in expected_tasks:
            self.assertTrue(dag.has_task(task_id), f"Task {task_id} not found in DAG")
    
    def test_task_dependencies(self):
        """Test that the task dependencies are set correctly"""
        # Test start -> get_batch_data
        start_task = dag.get_task("start")
        get_batch_task = dag.get_task("get_batch_data")
        self.assertIn(get_batch_task, start_task.downstream_list)
        
        # Test get_batch_data -> process_emails_batch
        process_emails_task = dag.get_task("process_emails_batch")
        self.assertIn(process_emails_task, get_batch_task.downstream_list)
        
        # Test process_emails_batch -> upload_raw_to_gcs
        upload_task = dag.get_task("upload_raw_to_gcs")
        self.assertIn(upload_task, process_emails_task.downstream_list)
        
        # Test upload_raw_to_gcs -> publish_metrics
        publish_metrics_task = dag.get_task("publish_metrics")
        self.assertIn(publish_metrics_task, upload_task.downstream_list)
        
        # Test upload_raw_to_gcs -> validation_task
        validation_task = dag.get_task("validation_task")
        self.assertIn(validation_task, upload_task.downstream_list)
        
        # Test validation_task -> trigger_preprocessing_pipeline
        trigger_task = dag.get_task("trigger_preprocessing_pipeline")
        self.assertIn(trigger_task, validation_task.downstream_list)
        
        # Test validation_task -> send_failure_email
        failure_task = dag.get_task("send_failure_email")
        self.assertIn(failure_task, validation_task.downstream_list)

    def test_task_trigger_rules(self):
        """Test that specific tasks have the correct trigger rules"""
        upload_task = dag.get_task("upload_raw_to_gcs")
        self.assertEqual(upload_task.trigger_rule, "none_failed")
        
        failure_task = dag.get_task("send_failure_email")
        self.assertEqual(failure_task.trigger_rule, "one_failed")

if __name__ == "__main__":
    unittest.main()