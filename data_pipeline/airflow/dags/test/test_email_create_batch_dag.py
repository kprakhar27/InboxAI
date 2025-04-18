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
    'tasks.email_batch_tasks': mock.MagicMock(),
    'tasks.email_fetch_tasks': mock.MagicMock(),
    'utils.airflow_utils': mock.MagicMock(),
}

# Set up the mocks
for module_name, mock_obj in mocks.items():
    sys.modules[module_name] = mock_obj

# Create specific function mocks needed by the DAG file
sys.modules['utils.gcp_logging_utils'].setup_gcp_logging = mock.MagicMock()
sys.modules['utils.gcp_logging_utils'].setup_gcp_logging.return_value = mock.MagicMock()
sys.modules['tasks.email_batch_tasks'].check_gmail_oauth2_credentials = mock.MagicMock()
sys.modules['tasks.email_batch_tasks'].create_batches = mock.MagicMock()
sys.modules['tasks.email_batch_tasks'].get_last_read_timestamp_task = mock.MagicMock()
sys.modules['tasks.email_batch_tasks'].trigger_email_get_for_batches = mock.MagicMock()
sys.modules['tasks.email_fetch_tasks'].send_failure_email = mock.MagicMock()
sys.modules['utils.airflow_utils'].create_db_session_task = mock.MagicMock()
sys.modules['utils.airflow_utils'].failure_callback = mock.MagicMock()
sys.modules['utils.airflow_utils'].get_email_for_dag_run = mock.MagicMock()
sys.modules['utils.airflow_utils'].get_user_id_for_dag_run = mock.MagicMock()

# Import Airflow modules and the DAG file
from airflow import DAG
from airflow.utils.task_group import TaskGroup
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator

# Import the actual DAG file
from email_01_create_batch_pipeline import dag

class TestEmailCreateBatchDAG(unittest.TestCase):
    """Test for email_create_batch_pipeline DAG"""
    
    def test_dag_id(self):
        """Test that the DAG ID is correct"""
        self.assertEqual(dag.dag_id, "email_create_batch_pipeline")
        
    def test_dag_default_args(self):
        """Test that the DAG has the expected default arguments"""
        self.assertEqual(dag.default_args["owner"], "airflow")
        self.assertEqual(dag.default_args["retries"], 3)
        
    def test_task_structure(self):
        """Test the structure of tasks in the DAG"""
        # Test that the start task exists
        self.assertTrue(dag.has_task("start"))
        
        # Test task group tasks
        task_groups = {
            "setup": ["get_email_for_dag_run", "get_user_id_for_dag_run", "check_db_session"],
            "auth_and_prep": ["check_gmail_oauth2_credentials", "get_last_read_timestamp_task"],
            "email_listing_group": ["fetch_emails_and_create_batches", "trigger_email_fetch_pipeline"]
        }
        
        for group_id, task_ids in task_groups.items():
            for task_id in task_ids:
                full_task_id = f"{group_id}.{task_id}"
                self.assertIn(full_task_id, dag.task_dict, f"Task {full_task_id} not found in DAG")
        
        # Test the failure notification task
        self.assertTrue(dag.has_task("send_failure_notification"))

if __name__ == "__main__":
    unittest.main()