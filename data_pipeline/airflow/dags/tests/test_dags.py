import unittest
from airflow.models import DagBag
from unittest.mock import MagicMock, patch

import sys

sys.modules["tasks.email_batch_tasks"] = MagicMock()
sys.modules["tasks.email_fetch_tasks"] = MagicMock()
sys.modules["services.storage_service"] = MagicMock()
sys.modules["tasks.email_embedding_tasks"] = MagicMock()
sys.modules["tasks.data_delete_task"] = MagicMock()
sys.modules["auth.gmail_auth"] = MagicMock()
sys.modules["services.gmail_service"] = MagicMock()
sys.modules["utils.preprocessing_utils"] = MagicMock()
sys.modules["tasks.email_preprocess_tasks"] = MagicMock()
sys.modules["utils.gcp_logging_utils"] = MagicMock()
sys.modules["utils.airflow_utils"] = MagicMock()
sys.modules["utils.db_utils"] = MagicMock()


class TestDAGs(unittest.TestCase):
    """Test suite for Airflow DAGs."""

    @classmethod
    def setUpClass(cls):
        """Load the DAGs for testing."""
        cls.dagbag = DagBag(dag_folder="./airflow/dags", include_examples=False)

    def test_dag_loaded(self):
        """Test if all DAGs are correctly loaded."""
        dag_ids = [
            "email_create_batch_pipeline",
            "monitoring_pipeline",
            "update_google_tokens",
            "email_embedding_generation_pipeline",
            "email_preprocessing_pipeline",
        ]
        for dag_id in dag_ids:
            with self.subTest(dag_id=dag_id):
                dag = self.dagbag.get_dag(dag_id)
                self.assertIsNotNone(dag, f"DAG '{dag_id}' is not loaded.")
                self.assertEqual(dag.dag_id, dag_id)

    def test_task_count(self):
        """Test if each DAG has the correct number of tasks."""
        expected_task_counts = {
            "email_create_batch_pipeline": 9,
            "monitoring_pipeline": 3,
            "update_google_tokens": 4,
            "email_embedding_generation_pipeline": 6,
            "email_preprocessing_pipeline": 6,
        }
        for dag_id, expected_count in expected_task_counts.items():
            with self.subTest(dag_id=dag_id):
                dag = self.dagbag.get_dag(dag_id)
                self.assertEqual(
                    len(dag.tasks),
                    expected_count,
                    f"DAG '{dag_id}' does not have the correct number of tasks.",
                )

    def test_task_documentation(self):
        """Test if all tasks have documentation."""
        dag_ids = [
            "email_create_batch_pipeline",
            "update_google_tokens",
        ]
        for dag_id in dag_ids:
            with self.subTest(dag_id=dag_id):
                dag = self.dagbag.get_dag(dag_id)
                for task in dag.tasks:
                    self.assertIsNotNone(
                        task.doc,
                        f"Task '{task.task_id}' in DAG '{dag_id}' does not have documentation.",
                    )

    def test_failure_notification_trigger_rule(self):
        """Test if failure notification tasks have the correct trigger rule."""
        failure_notification_tasks = {
            "update_google_tokens": "send_failure_notification",
            "email_embedding_generation_pipeline": "send_failure_email",
            "email_preprocessing_pipeline": "send_failure_email",
        }
        for dag_id, task_id in failure_notification_tasks.items():
            with self.subTest(dag_id=dag_id):
                dag = self.dagbag.get_dag(dag_id)
                task = dag.get_task(task_id)
                self.assertEqual(
                    task.trigger_rule,
                    "one_failed",
                    f"Task '{task_id}' in DAG '{dag_id}' does not have the correct trigger rule.",
                )


if __name__ == "__main__":
    unittest.main()
