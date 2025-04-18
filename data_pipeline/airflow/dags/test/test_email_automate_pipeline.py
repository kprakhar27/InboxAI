import unittest
import os
import sys
from unittest import mock
from datetime import timedelta

# Add project root to Python path 
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Mock all required imported modules to avoid dependency issues
mocks = {
    'utils.gcp_logging_utils': mock.MagicMock(),
    'utils.airflow_utils': mock.MagicMock(),
    'utils.db_utils': mock.MagicMock(),
}

# Set up the mocks
for module_name, mock_obj in mocks.items():
    sys.modules[module_name] = mock_obj

# Create specific function mocks needed by the DAG file
sys.modules['utils.gcp_logging_utils'].setup_gcp_logging = mock.MagicMock()
sys.modules['utils.gcp_logging_utils'].setup_gcp_logging.return_value = mock.MagicMock()
sys.modules['utils.airflow_utils'].failure_callback = mock.MagicMock()
sys.modules['utils.db_utils'].get_db_session = mock.MagicMock()

# Mock session object for database operations
mock_session = mock.MagicMock()
mock_results = mock.MagicMock()
mock_results.execute.return_value = [
    (1, "user1", "user1@example.com"),
    (2, "user2", "user2@example.com")
]
sys.modules['utils.db_utils'].get_db_session.return_value = mock_session

# Import Airflow modules
from airflow import DAG
from airflow.decorators import task
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.utils.dates import days_ago

# Import the actual DAG file - note that for task decorator testing, we may need special handling
try:
    from email_00_automate_pipeline import dag, fetch_users
except Exception as e:
    print(f"Error importing DAG: {e}")

class TestEmailAutomatePipeline(unittest.TestCase):
    """Test for email_00_automate_pipeline DAG"""
    
    def test_dag_id(self):
        """Test that the DAG ID is correct"""
        self.assertEqual(dag.dag_id, "email_00_automate_pipeline")
        
    def test_dag_default_args(self):
        """Test that the DAG has the expected default arguments"""
        self.assertEqual(dag.default_args["owner"], "airflow")
        self.assertEqual(dag.default_args["retries"], 3)
        self.assertTrue("on_failure_callback" in dag.default_args)
        
    def test_schedule_interval(self):
        """Test that the schedule interval is set correctly"""
        self.assertEqual(dag.schedule_interval, "*/6 * * * *")
        
    def test_max_active_runs(self):
        """Test that max_active_runs is set correctly"""
        self.assertEqual(dag.max_active_runs, 5)
        
    def test_catchup(self):
        """Test that catchup is set correctly"""
        self.assertFalse(dag.catchup)
        
    def test_tags(self):
        """Test that tags are set correctly"""
        self.assertIn("cron", dag.tags)
        self.assertIn("trigger", dag.tags)
        self.assertIn("dynamic", dag.tags)
        
    def test_task_exists(self):
        """Test that task mapping task exists in some form"""
        # For task-mapped operations, we need to check if the base task exists
        # This is a bit different than regular tasks due to the expand() operation
        found = False
        for task in dag.tasks:
            if task.task_id.startswith("trigger_pipeline"):
                found = True
                break
        self.assertTrue(found, "No task found with ID starting with 'trigger_pipeline'")
        

    def test_trigger_dag_properties(self):
        """Test properties of the trigger DAG task"""
        # Find the base trigger task
        trigger_task = None
        for task in dag.tasks:
            if task.task_id.startswith("trigger_pipeline"):
                trigger_task = task
                break
        self.assertIsNotNone(trigger_task)
    
    # Check if it's a mapped task (which is the case here)
        if hasattr(trigger_task, 'operator_class'):
            # For mapped tasks, check the operator_class attribute
            self.assertEqual(trigger_task.operator_class.__name__, "TriggerDagRunOperator")
        else:
            # For direct tasks, check the instance type
            self.assertIsInstance(trigger_task, TriggerDagRunOperator)
    
        # Test that it triggers the correct DAG - adapting for mapped operators
        if hasattr(trigger_task, 'partial_kwargs'):
            self.assertEqual(trigger_task.partial_kwargs.get('trigger_dag_id'), "email_create_batch_pipeline")
            # Test that wait_for_completion is False
            self.assertEqual(trigger_task.partial_kwargs.get('wait_for_completion'), False)

    def test_failure_scenario(self):
        """Test that the DAG handles failures correctly"""
    # Mock the fetch_users task to raise an exception
        with mock.patch('email_00_automate_pipeline.fetch_users', side_effect=Exception("Database connection failed")):
            self.assertIsNotNone(dag.default_args.get("on_failure_callback"))   # Check that the failure callback is set in default_args
            self.assertEqual(dag.default_args.get("retries"), 3)   # Check that retries are set properly
            self.assertIsInstance(dag.default_args.get("retry_delay"), timedelta)   # Check that retry_delay is set properly
            self.assertEqual(dag.default_args.get("retry_delay").total_seconds(), 300)  # 5 minutes in seconds
            self.assertTrue(dag.default_args.get("email_on_failure"))  # Check that email_on_failure is set to True

if __name__ == "__main__":
    unittest.main()




