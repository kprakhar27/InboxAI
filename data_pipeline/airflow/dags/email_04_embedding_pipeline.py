import logging
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from tasks.email_embedding_tasks import (
    download_processed_from_gcs,
    generate_embeddings,
    upsert_embeddings,
)
from tasks.email_fetch_tasks import send_failure_email, send_success_email

# Initialize logging
logger = logging.getLogger(__name__)

LOCAL_TMP_DIR = "/tmp/inboxai_embedding"

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
    dag_id="email_embedding_generation_pipeline",
    default_args=default_args,
    description="Email preprocessing pipeline for embedding generation",
    catchup=False,
    max_active_runs=1,
    tags=["email", "embeddings"],
) as dag:

    logger.info("Initializing email embedding pipeline DAG")

    # Task 1: Start the pipeline
    start = EmptyOperator(
        task_id="start",
        doc="Start of the email preprocessing pipeline.",
    )

    # Task 2: Download processed data from GCS
    download_processed_data = PythonOperator(
        task_id="download_processed_data",
        python_callable=download_processed_from_gcs,
        provide_context=True,
    )

    # Task 2: Generate embeddings
    generate_embeddings_task = PythonOperator(
        task_id="generate_embeddings",
        python_callable=generate_embeddings,
        provide_context=True,
    )

    # Task 4: Upsert embeddings to Chroma Vector Database
    upsert_embeddings = PythonOperator(
        task_id="upsert_embeddings",
        python_callable=upsert_embeddings,
        provide_context=True,
    )

    # Task 5: Send Success Email
    send_success = PythonOperator(
        task_id="send_success_email",
        python_callable=send_success_email,
        provide_context=True,
        trigger_rule="all_success",
        doc="Sends a success email if all tasks in the pipeline succeed.",
        on_success_callback=lambda context: logger.info(
            f"Email preprocessing pipeline succeeded for date: {context['ds']}"
        ),
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

    # Define dependencies
    start >> download_processed_data >> generate_embeddings_task >> upsert_embeddings
    upsert_embeddings >> send_success >> send_failure
