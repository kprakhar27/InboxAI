import logging
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from tasks.email_fetch_tasks import send_failure_email
from tasks.email_preprocess_tasks import (
    download_raw_from_gcs,
    preprocess_emails,
    trigger_embedding_pipeline,
    upload_processed_to_gcs,
)

# Initialize logging
logger = logging.getLogger(__name__)

# Configuration
GCS_BUCKET = "{{ var.value.gcs_bucket }}"
RAW_DATA_PATH = "raw/emails"
PROCESSED_DATA_PATH = "processed/emails"
LOCAL_TMP_DIR = "/tmp/inboxai_preprocessing"

# Ensure the temporary directory exists
os.makedirs(LOCAL_TMP_DIR, exist_ok=True)
logger.info(f"Temporary directory created/verified: {LOCAL_TMP_DIR}")

# Default arguments
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

# DAG definition
with DAG(
    dag_id="email_preprocessing_pipeline",
    default_args=default_args,
    description="Email preprocessing pipeline for embedding generation",
    start_date=datetime(2023, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["email", "preprocessing", "embeddings"],
) as dag:

    logger.info("Initializing email preprocessing pipeline DAG")

    # Task 1: Start the pipeline
    start = EmptyOperator(
        task_id="start",
        doc="Start of the email preprocessing pipeline.",
    )

    # Task 2: Download raw data from GCS
    download_raw_data = PythonOperator(
        task_id="download_raw_data",
        python_callable=download_raw_from_gcs,
        provide_context=True,
    )

    # Task 3: Preprocess emails
    preprocess_emails_task = PythonOperator(
        task_id="preprocess_emails",
        python_callable=preprocess_emails,
        provide_context=True,
    )

    # Task 4: Upload processed data to GCS
    upload_processed_data = PythonOperator(
        task_id="upload_processed_data",
        python_callable=upload_processed_to_gcs,
        provide_context=True,
    )

    # Task 5: Trigger embedding pipeline
    trigger_embedding_dag = PythonOperator(
        task_id="trigger_embedding_pipeline",
        python_callable=trigger_embedding_pipeline,
        provide_context=True,
        doc="Triggers the embedding generation pipeline if preprocessing is successful.",
    )

    # Task 6: Send Failure Email
    send_failure = PythonOperator(
        task_id="send_failure_email",
        python_callable=send_failure_email,
        provide_context=True,
        trigger_rule="one_failed",
        doc="Sends a failure email if any task in the pipeline fails.",
        on_failure_callback=lambda context: logger.error(
            f"Email preprocessing pipeline failed for date: {context['ds']}"
        ),
    )

    # Task dependencies should be changed
    # First define the main flow

    # Set up main success path
    (
        start
        >> download_raw_data
        >> preprocess_emails_task
        >> upload_processed_data
        >> trigger_embedding_dag
        >> send_failure
    )

    logger.info("Email preprocessing pipeline DAG configuration complete")
