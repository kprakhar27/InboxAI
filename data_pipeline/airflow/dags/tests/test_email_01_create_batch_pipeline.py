import unittest
from airflow.models import DagBag
from unittest.mock import MagicMock, patch
from airflow.utils import db as airflow_db

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
sys.modules["models_postgres"] = MagicMock()
sys.modules["models_pydantic"] = MagicMock()


class TestEmailCreateBatchPipelineDAG(unittest.TestCase):
    """Test suite for the email_01_create_batch_pipeline DAG."""

    @classmethod
    def setUpClass(cls):
        """Load the DAG for testing."""
        airflow_db.resetdb()
        airflow_db.initdb()
        with patch.dict(
            "sys.modules",
            {
                "utils.airflow_utils": MagicMock(),
                "utils.db_utils": MagicMock(),
                "utils.gcp_logging_utils": MagicMock(),
            },
        ):
            cls.dagbag = DagBag(dag_folder="./airflow/dags", include_examples=False)

    def test_dag_loaded(self):
        """Test if the DAG is correctly loaded."""
        dag_id = "email_create_batch_pipeline"
        dag = self.dagbag.get_dag(dag_id)
        self.assertIsNotNone(dag, f"DAG '{dag_id}' is not loaded.")
        self.assertEqual(dag.dag_id, dag_id)

    def test_failure_notification_trigger_rule(self):
        """Test if the failure notification task has the correct trigger rule."""
        dag_id = "email_create_batch_pipeline"
        dag = self.dagbag.get_dag(dag_id)

        failure_notification_task = dag.get_task("send_failure_notification")
        self.assertEqual(
            failure_notification_task.trigger_rule,
            "one_failed",
            "Failure notification task does not have the correct trigger rule.",
        )


if __name__ == "__main__":
    unittest.main()
