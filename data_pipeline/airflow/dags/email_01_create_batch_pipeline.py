import logging
from datetime import timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from airflow.utils.task_group import TaskGroup
from tasks.email_batch_tasks import (
    check_gmail_oauth2_credentials,
    create_batches,
    get_last_read_timestamp_task,
    trigger_email_get_for_batches,
)
from tasks.email_fetch_tasks import send_failure_email
from utils.airflow_utils import (
    create_db_session_task,
    failure_callback,
    get_email_for_dag_run,
    get_user_id_for_dag_run,
)
from utils.gcp_logging_utils import setup_gcp_logging

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
    dag_id="email_create_batch_pipeline",
    default_args=default_args,
    description="Email Fetch Pipeline: Fetches emails and creates batches for preprocessing.",
    schedule_interval=None,
    catchup=False,
    max_active_runs=4,
    tags=["email", "fetch", "pipeline"],
    params={
        "email_address": "",
        "user_id": "",
    },
) as dag:
    """
    ### Email Fetch Pipeline

    This DAG performs the following steps:
    1. Fetches the email address from the DAG run configuration.
    2. Creates a database session.
    3. Checks Gmail OAuth2 credentials.
    4. Gets the last read timestamp from the database.
    5. Fetches emails and creates batches of 50 emails.
    6. Triggers the preprocessing pipeline for each batch.
    """
    logger.info("Initializing Email Fetch Pipeline DAG")

    # Task 1: Start
    start = EmptyOperator(
        task_id="start",
        doc="Start of the pipeline.",
    )
    logger.info("Start task initialized")

    # Setup Task Group
    with TaskGroup(group_id="setup") as setup_group:
        # Task 2: Get Email from Dag Run
        get_email = PythonOperator(
            task_id="get_email_for_dag_run",
            python_callable=get_email_for_dag_run,
            provide_context=True,
            doc="Fetches the email address from the DAG run configuration.",
        )

        # Task: Get User ID for Email
        get_user_id = PythonOperator(
            task_id="get_user_id_for_dag_run",
            python_callable=get_user_id_for_dag_run,
            provide_context=True,
            doc="Gets the user ID from the DAG run configuration.",
        )

        # Task 3: Create DB Session
        check_db_session = PythonOperator(
            task_id="check_db_session",
            python_callable=create_db_session_task,
            provide_context=True,
            doc="Creates a database session for the pipeline.",
        )

        # Define setup tasks dependencies
        get_email >> get_user_id >> check_db_session

    # Authentication & Preparation Task Group
    with TaskGroup(group_id="auth_and_prep") as auth_prep_group:
        # Task 4: Check Gmail OAuth2 Credentials
        check_gmail_credentials = PythonOperator(
            task_id="check_gmail_oauth2_credentials",
            python_callable=check_gmail_oauth2_credentials,
            provide_context=True,
            doc="Checks Gmail OAuth2 credentials for the given email address.",
        )

        # Task 5: Get Last Read Timestamp from DB for Email
        get_last_read_timestamp = PythonOperator(
            task_id="get_last_read_timestamp_task",
            python_callable=get_last_read_timestamp_task,
            provide_context=True,
            doc="Fetches the last read timestamp from the database for the given email address.",
        )

        # Configure parallel tasks
        [check_gmail_credentials, get_last_read_timestamp]

    # Email Processing Task Group
    with TaskGroup(group_id="email_listing_group") as email_listing_group:
        # Task 6: Fetch Emails and Create Batches
        fetch_emails_and_create_batches = PythonOperator(
            task_id="fetch_emails_and_create_batches",
            python_callable=create_batches,
            provide_context=True,
            doc="Fetches emails and creates batches of 50 emails.",
        )

        # Task 7: Trigger Preprocessing Pipeline for Each Batch
        trigger_email_get_for_batches = PythonOperator(
            task_id="trigger_email_fetch_pipeline",
            python_callable=trigger_email_get_for_batches,
            op_kwargs={"dag": dag},
            provide_context=True,
            doc="Triggers the preprocessing pipeline for each batch of emails.",
        )

        # Define processing task dependencies
        fetch_emails_and_create_batches >> trigger_email_get_for_batches

    # Add this as a new task at the end of your DAG definition
    send_failure_notification = PythonOperator(
        task_id="send_failure_notification",
        python_callable=send_failure_email,
        provide_context=True,
        trigger_rule="one_failed",
        doc="Sends a failure notification email if any task in the pipeline fails.",
    )
    logger.info("Send failure notification task initialized")

    # Define the main workflow with TaskGroups
    logger.info("Setting up task dependencies")
    (
        start
        >> setup_group
        >> auth_prep_group
        >> email_listing_group
        >> send_failure_notification
    )

    logger.info("Email Fetch Pipeline DAG fully initialized")
