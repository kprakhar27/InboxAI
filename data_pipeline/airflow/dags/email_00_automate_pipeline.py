import logging
from datetime import timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from airflow.utils.task_group import TaskGroup
from tasks.email_automation_task import automate_data_pipeline
from utils.airflow_utils import (
    failure_callback
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": failure_callback,
    "schedule_interval": "*/6 * * * *"
}

with DAG(
    dag_id="email_automation",
    default_args=default_args,
    description="Email automation Pipeline: Triggers data ingestion pipeline",
    catchup=False,
    max_active_runs=1,
    tags=["email", "fetch", "pipeline"],
) as dag:
    logger.info("Initialized DAG for automating the pipeline")
    start = EmptyOperator(
        task_id="start",
        doc="Start of the pipeline.",
    )
    logger.info("Start task initialized")

    
    trigger_pipeline = PythonOperator(
            task_id="trigger_pipeline",
            python_callable=automate_data_pipeline,
            provide_context=True,
            doc="Triggers data pipeline hourly",
        )
    start >> trigger_pipeline