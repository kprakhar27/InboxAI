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


class TestDagIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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
        dag = self.dagbag.get_dag(dag_id="email_00_automate_pipeline")
        assert self.dagbag.import_errors == {}
        self.assertIsNotNone(dag)
        self.assertEqual(dag.schedule_interval, "*/6 * * * *")
        self.assertEqual(dag.tags, ["cron", "trigger", "dynamic"])
