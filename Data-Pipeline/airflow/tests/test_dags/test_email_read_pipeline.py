import pytest
from airflow.models import DagBag
from airflow.utils.task_group import TaskGroup


class TestEmailReadPipeline:

    @pytest.fixture
    def dagbag(self):
        """Get a DagBag with our DAGs loaded"""
        return DagBag(dag_folder="airflow/dags")

    def test_dag_loaded(self, dagbag):
        """Test that our DAG is loaded correctly"""
        dag = dagbag.get_dag("email_processing_pipeline_v2")
        assert dagbag.import_errors == {}
        assert dag is not None
        assert len(dag.tasks) > 0

    def test_dag_structure(self, dagbag):
        """Test the structure of our DAG"""
        dag = dagbag.get_dag("email_processing_pipeline_v2")

        # Core tasks
        task_ids = [task.task_id for task in dag.tasks]
        expected_tasks = [
            "start",
            "get_email_for_dag_run",
            "check_db_session",
            "choose_processing_path",
            "trigger_preprocessing_pipeline",
            "send_failure_email",
        ]

        for task in expected_tasks:
            assert task in task_ids

        # Task groups
        task_groups = [
            group.group_id for group in dag.task_groups if isinstance(group, TaskGroup)
        ]
        expected_groups = [
            "initialization",
            "email_processing",
            "data_upload",
            "post_processing",
        ]

        for group in expected_groups:
            assert group in task_groups

    def test_dependencies(self, dagbag):
        """Test that task dependencies are set up correctly"""
        dag = dagbag.get_dag("email_processing_pipeline_v2")

        # Test start dependencies
        start_task = dag.get_task("start")
        assert len(start_task.downstream_task_ids) == 2
        assert "get_email_for_dag_run" in start_task.downstream_task_ids
        assert "check_db_session" in start_task.downstream_task_ids

        # Test branching task
        branch_task = dag.get_task("choose_processing_path")
        assert len(branch_task.downstream_task_ids) == 2
        assert (
            "email_processing.process_emails_batch" in branch_task.downstream_task_ids
        )
        assert (
            "email_processing.process_emails_minibatch"
            in branch_task.downstream_task_ids
        )
