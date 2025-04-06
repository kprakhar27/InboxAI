import logging
from datetime import timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from tasks.data_delete_task import (
    delete_embeddings,
    delete_from_gcp,
    delete_from_postgres,
)
from tasks.email_fetch_tasks import send_failure_email
from utils.airflow_utils import failure_callback

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
}

with DAG(
    dag_id="data_deletion_pipeline",
    default_args=default_args,
    description="Email data deletion Pipeline",
    schedule_interval=None,
    catchup=False,
    max_active_runs=1,
    tags=["email", "delete", "pipeline"],
) as dag:
    logger.info("Initialized DAG for deletion of user data the pipeline")
    start = EmptyOperator(
        task_id="start",
        doc="Start of the pipeline.",
    )
    logger.info("Start task initialized")

    # Task 1: Delete Embeddings from vector database
    vector_db_delete = PythonOperator(
        task_id="vector_db_delete",
        python_callable=delete_embeddings,
        provide_context=True,
        doc="deletes embeddings data associated with user_id and email_id",
    )
    # Task 2: Delete from GCP
    gcp_delete = PythonOperator(
        task_id="gcp_delete",
        python_callable=delete_from_gcp,
        provide_context=True,
        doc="deletes all the gcp folder data associated with user_id and email_id",
    )
    # Task 3: Delete postgres token
    postgres_delete = PythonOperator(
        task_id="postgres_delete",
        python_callable=delete_from_postgres,
        provide_context=True,
        doc="deletes postgres user email data",
    )

    # Task 4: send failure notification
    send_failure_notification = PythonOperator(
        task_id="send_failure_notification",
        python_callable=send_failure_email,
        provide_context=True,
        trigger_rule="one_failed",
        doc="Sends a failure notification email if any task in the pipeline fails.",
    )
    logger.info("Send failure notification task initialized")
    (
        start
        >> vector_db_delete
        >> gcp_delete
        >> postgres_delete
        >> send_failure_notification
    )
