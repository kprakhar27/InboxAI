import logging
from datetime import timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.utils.dates import days_ago
from airflow.utils.task_group import TaskGroup
from tasks.email_read_tasks import (
    check_gmail_oauth2_credentials,
    choose_processing_path,
    get_last_read_timestamp_task,
    process_emails_batch,
    process_emails_minibatch,
    publish_metrics_task,
    send_failure_email,
    trigger_preprocessing_pipeline,
    upload_raw_data_to_gcs,
    validation_task,
)
from utils.airflow_utils import (
    create_db_session_task,
    failure_callback,
    get_email_for_dag_run,
)

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
    dag_id="email_processing_pipeline_v2",
    schedule_interval="0 */6 * * *",
    default_args=default_args,
    description="Email Processing Pipeline: Fetches emails, processes them, and uploads data to GCS.",
    catchup=False,
    max_active_runs=1,
    tags=["email", "processing", "pipeline"],
    params={
        "email_address": "pc612001@gmail.com",  # Default email address
        "batch_size": 100,  # Default batch size
    },
) as dag:
    """
    ### Email Processing Pipeline (Improved)

    This DAG performs the following steps:
    1. Fetches the email address from the DAG run configuration.
    2. Creates a database session.
    3. Checks Gmail OAuth2 credentials.
    4. Gets the last read timestamp from the database.
    5. Chooses the processing path (batch or mini-batch).
    6. Processes emails in batches based on the chosen path.
    7. Uploads raw data to Google Cloud Storage in batches.
    8. Publishes metrics and performs data validation.
    9. Triggers the preprocessing pipeline or sends a failure email.
    """

    # Start
    start = EmptyOperator(
        task_id="start",
        doc="Start of the pipeline.",
        dag=dag,
    )

    # Task 1: Get Email from Dag Run
    get_email = PythonOperator(
        task_id="get_email_for_dag_run",
        python_callable=get_email_for_dag_run,
        provide_context=True,
        doc="Fetches the email address from the DAG run configuration.",
        dag=dag,
    )

    # Task 2: Create DB Session
    check_db_session = PythonOperator(
        task_id="check_db_session",
        python_callable=create_db_session_task,
        provide_context=True,
        doc="Creates a database session for the pipeline.",
        dag=dag,
    )

    # Task Group: Initialization
    with TaskGroup(group_id="initialization") as initialization:
        # Task 3: Check Gmail OAuth2 Credentials
        check_gmail_credentials = PythonOperator(
            task_id="check_gmail_oauth2_credentials",
            python_callable=check_gmail_oauth2_credentials,
            provide_context=True,
            doc="Checks Gmail OAuth2 credentials for the given email address.",
            dag=dag,
        )

        # Task 4: Get Last Read Timestamp from DB for Email
        get_last_read_timestamp = PythonOperator(
            task_id="get_last_read_timestamp_task",
            python_callable=get_last_read_timestamp_task,
            provide_context=True,
            doc="Fetches the last read timestamp from the database for the given email address.",
            dag=dag,
        )

    # Task 5: Choose Processing Path (Branching)
    choose_read_path = BranchPythonOperator(
        task_id="choose_processing_path",
        python_callable=choose_processing_path,
        provide_context=True,
        doc="Chooses the processing path (batch or mini-batch) based on the time difference since the last read.",
        dag=dag,
    )

    # Task Group: Email Processing
    with TaskGroup(group_id="email_processing") as email_processing:
        # Task 6a: Process Emails in Batch
        process_emails_batch = PythonOperator(
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

        # Task 6b: Process Emails in Minibatch
        process_emails_minibatch = PythonOperator(
            task_id="process_emails_minibatch",
            python_callable=process_emails_minibatch,
            provide_context=True,
            doc="Processes emails in mini-batch mode.",
            retries=3,
            retry_delay=timedelta(seconds=60),
            retry_exponential_backoff=True,
            max_retry_delay=timedelta(minutes=10),
            dag=dag,
        )

    # Task Group: Data Upload
    with TaskGroup(group_id="data_upload") as data_upload:
        # Task 7: Upload Raw Data to GCS
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

    # Task Group: Post Processing
    with TaskGroup(group_id="post_processing") as post_processing:
        # Task 8: Publish Metrics
        publish_metrics = PythonOperator(
            task_id="publish_metrics",
            python_callable=publish_metrics_task,
            provide_context=True,
            doc="Publishes metrics for the pipeline.",
            dag=dag,
        )

        # Task 9: Data Validation
        data_validation = PythonOperator(
            task_id="data_validation",
            python_callable=validation_task,
            provide_context=True,
            doc="Performs data validation on the processed emails.",
            dag=dag,
        )

    # Task 10: Trigger Preprocessing Pipeline
    trigger_preprocessing_pipeline = PythonOperator(
        task_id="trigger_preprocessing_pipeline",
        python_callable=trigger_preprocessing_pipeline,
        trigger_rule="none_failed",
        provide_context=True,
        doc="Triggers the preprocessing pipeline if data validation is successful.",
        dag=dag,
    )

    # Task 11: Send Failure Email
    send_failure_email = PythonOperator(
        task_id="send_failure_email",
        python_callable=send_failure_email,
        trigger_rule="one_failed",
        provide_context=True,
        doc="Sends a failure email if data validation fails.",
        dag=dag,
    )

    # Define the workflow
    start >> [get_email, check_db_session] >> initialization >> choose_read_path

    choose_read_path >> [
        process_emails_batch,
        process_emails_minibatch,
    ]

    [process_emails_batch, process_emails_minibatch] >> upload_raw_to_gcs

    upload_raw_to_gcs >> [publish_metrics, data_validation]

    data_validation >> [trigger_preprocessing_pipeline, send_failure_email]
