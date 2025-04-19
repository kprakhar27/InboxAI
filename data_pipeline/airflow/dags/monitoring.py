import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from tasks.email_fetch_tasks import send_monitoring_email
from utils.airflow_utils import (
    create_db_session_task,
    failure_callback,
    monitoring_function,
)
from utils.gcp_logging_utils import setup_gcp_logging

logger = logging.getLogger("airflow.task")

# Initialize logger
logger = setup_gcp_logging("email_01_create_batch_pipeline")
logger.info("Initialized logger for email_01_create_batch_pipeline")

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": failure_callback,
}

with DAG(
    dag_id="monitoring_pipeline",
    default_args=default_args,
    description="Airflow DAG for daily_observability_metrics",
    schedule_interval="@daily",  # Fixed syntax: added quotes
    catchup=False,
    max_active_runs=4,
    start_date=datetime(2025, 4, 19),
    tags=["monitoring", "observability"],
) as dag:
    """
    ### Monitoring Pipeline
    This DAG performs the following steps:
    1. Creates a database session.
    2. Checks the status of the monitoring pipeline.
    3. Sends an email alert if the pipeline fails.
    """

    # Task 1: Start
    start_task = EmptyOperator(
        task_id="start",
        dag=dag,
    )
    logger.info("Start task initialized")

    # Task 2: Check Monitoring Pipeline Status
    check_monitoring_status = PythonOperator(
        task_id="check_monitoring_status",
        python_callable=monitoring_function,
        provide_context=True,
        dag=dag,
    )
    logger.info("Monitoring status check task initialized")

    # Task 4: Send Email Alert
    send_email_alert = PythonOperator(
        task_id="send_email_alert",
        python_callable=send_monitoring_email,
        provide_context=True,
        dag=dag,
    )
    logger.info("Email alert task initialized")

    # Setup Task Dependencies
    start_task >> check_monitoring_status >> send_email_alert
