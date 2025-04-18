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
    'tasks.email_preprocess_tasks': mock.MagicMock(),
}

# Set up the mocks
for module_name, mock_obj in mocks.items():
    sys.modules[module_name] = mock_obj

# Create specific function mocks needed by the DAG file
sys.modules['utils.gcp_logging_utils'].setup_gcp_logging = mock.MagicMock()
sys.modules['utils.gcp_logging_utils'].setup_gcp_logging.return_value = mock.MagicMock()
sys.modules['tasks.email_fetch_tasks'].send_failure_email = mock.MagicMock()
sys.modules['tasks.email_preprocess_tasks'].download_raw_from_gcs = mock.MagicMock()
sys.modules['tasks.email_preprocess_tasks'].preprocess_emails = mock.MagicMock()
sys.modules['tasks.email_preprocess_tasks'].trigger_embedding_pipeline = mock.MagicMock()
sys.modules['tasks.email_preprocess_tasks'].upload_processed_to_gcs = mock.MagicMock()

# Import Airflow modules and the DAG file
from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator

# Mock os.makedirs to avoid actual directory creation
original_makedirs = os.makedirs
os.makedirs = mock.MagicMock()

# Import the actual DAG file
try:
    from email_03_preprocessing_pipeline import dag
finally:
    # Restore original os.makedirs
    os.makedirs = original_makedirs

class TestEmailPreprocessingPipeline(unittest.TestCase):
    """Test for email_preprocessing_pipeline DAG"""
    
    def test_dag_id(self):
        """Test that the DAG ID is correct"""
        self.assertEqual(dag.dag_id, "email_preprocessing_pipeline")
        
    def test_dag_default_args(self):
        """Test that the DAG has the expected default arguments"""
        self.assertEqual(dag.default_args["owner"], "airflow")
        self.assertEqual(dag.default_args["retries"], 2)
        self.assertEqual(dag.default_args["email_on_failure"], False)
        
    def test_task_structure(self):
        """Test the structure of tasks in the DAG"""
        # Define the expected tasks
        expected_tasks = [
            "start",
            "download_raw_data",
            "preprocess_emails",
            "upload_processed_data",
            "trigger_embedding_pipeline",
            "send_failure_email"
        ]
        
        # Check that all expected tasks exist
        for task_id in expected_tasks:
            self.assertTrue(dag.has_task(task_id), f"Task {task_id} not found in DAG")
    
    def test_task_dependencies(self):
        """Test that the task dependencies are set correctly"""
        # Define task sequence
        task_sequence = [
            "start",
            "download_raw_data",
            "preprocess_emails",
            "upload_processed_data", 
            "trigger_embedding_pipeline",
            "send_failure_email"
        ]
        
        # Check linear dependencies
        for i in range(len(task_sequence) - 1):
            upstream_task = dag.get_task(task_sequence[i])
            downstream_task = dag.get_task(task_sequence[i + 1])
            self.assertIn(downstream_task, upstream_task.downstream_list, 
                          f"{task_sequence[i]} should be upstream of {task_sequence[i + 1]}")
    
    def test_failure_task_trigger_rule(self):
        """Test that the failure task has the correct trigger rule"""
        failure_task = dag.get_task("send_failure_email")
        self.assertEqual(failure_task.trigger_rule, "one_failed")
        
    def test_max_active_runs(self):
        """Test that max_active_runs is set correctly"""
        self.assertEqual(dag.max_active_runs, 1)

if __name__ == "__main__":
    unittest.main()




