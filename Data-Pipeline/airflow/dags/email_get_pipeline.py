import logging
from datetime import timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.utils.dates import days_ago
from airflow.utils.task_group import TaskGroup
from tasks.email_read_tasks import (
    get_batch_data_from_trigger,
    process_emails_batch,
    publish_metrics_task,
    send_failure_email,
    trigger_preprocessing_pipeline,
    upload_raw_data_to_gcs,
    validation_task,
)
from utils.airflow_utils import failure_callback

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

default_args = {
    "owner": "airflow",
    "start_date": days_ago(1),
    "depends_on_past": False,
    "email": ["prad@inboxai.tech"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": failure_callback,  # Global failure callback
}

with DAG(
    dag_id="email_get_pipeline",
    default_args=default_args,
    description="Email Get Pipeline: Processes batches of emails.",
    catchup=False,
    max_active_runs=4,
    tags=["email", "get", "pipeline"],
) as dag:
    """
    ### Email Get Pipeline

    This DAG performs the following steps:
    1. Processes emails in batches.
    2. Uploads raw data to Google Cloud Storage.
    3. Publishes metrics and performs data validation.
    4. Triggers the preprocessing pipeline or sends a failure email.
    """

    # Start
    start = EmptyOperator(
        task_id="start",
        doc="Start of the pipeline.",
        dag=dag,
    )

    # Task 1: Get batch data from trigger
    get_batch = PythonOperator(
        task_id="get_batch_data",
        python_callable=get_batch_data_from_trigger,
        provide_context=True,
        doc="Extracts batch data from the triggering DAG run.",
    )

    # Task 2: Process emails in batch mode
    process_emails = PythonOperator(
        task_id="process_emails_batch",
        python_callable=process_emails_batch,
        provide_context=True,
        doc="Processes emails in batch mode.",
        retries=3,
        retry_delay=timedelta(seconds=60),
        retry_exponential_backoff=True,
        max_retry_delay=timedelta(minutes=10),
        dag=dag,
    )

    # Task 3: Upload raw data to GCS
    upload_raw_to_gcs = PythonOperator(
        task_id="upload_raw_to_gcs",
        python_callable=upload_raw_data_to_gcs,
        trigger_rule="none_failed",
        provide_context=True,
        doc="Uploads raw email data to Google Cloud Storage in batches.",
        retries=3,
        retry_delay=timedelta(minutes=5),
        dag=dag,
    )

    # Task 4: Publish Metrics
    publish_metrics = PythonOperator(
        task_id="publish_metrics",
        python_callable=publish_metrics_task,
        provide_context=True,
        doc="Publishes metrics for the pipeline.",
        dag=dag,
    )

    # Task 5: Data Validation
    data_validation = PythonOperator(
        task_id="validation_task",
        python_callable=validation_task,
        provide_context=True,
        doc="Performs data validation on the processed emails.",
        dag=dag,
    )

    # Task 6: Trigger Preprocessing Pipeline
    trigger_preprocessing = PythonOperator(
        task_id="trigger_preprocessing_pipeline",
        python_callable=trigger_preprocessing_pipeline,
        provide_context=True,
        doc="Triggers the preprocessing pipeline if data validation is successful.",
        dag=dag,
    )

    # Task 7: Send Failure Email
    send_failure = PythonOperator(
        task_id="send_failure_email",
        python_callable=send_failure_email,
        provide_context=True,
        doc="Sends a failure email if data validation fails.",
        dag=dag,
    )

# Define the workflow
start >> get_batch >> process_emails >> upload_raw_to_gcs
upload_raw_to_gcs >> publish_metrics
upload_raw_to_gcs >> data_validation

# Branch based on validation result
data_validation >> trigger_preprocessing
data_validation >> send_failure
