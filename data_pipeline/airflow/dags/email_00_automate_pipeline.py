import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.decorators import task
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.utils.dates import days_ago

# from tasks.email_automation_task import automate_data_pipeline, fetch_users
from utils.airflow_utils import failure_callback
from utils.db_utils import get_db_session

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

default_args = {
    "owner": "airflow",
    "start_date": days_ago(1),
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": failure_callback,
}


@task
def fetch_users(**context):
    # Simulating a database or API call
    try:
        logger.info("connecting to Database....")
        session = get_db_session()
        results = session.execute("select * from google_tokens")
        user_list = [
            {"user_id": str(result[1]), "email_address": result[2]}
            for result in results
        ]
        logger.info("Retrived users from DB")
        session.close()
        return user_list
    except Exception as e:
        logger.error(f"Error in triggering data pipeline: {e}")
        raise


# Define the DAG
with DAG(
    dag_id="email_00_automate_pipeline",
    default_args=default_args,
    description="Dynamically trigger email batch pipeline for each user",
    schedule_interval="*/6 * * * *",  # Runs every 6 hours
    catchup=False,
    max_active_runs=5,
    tags=["cron", "trigger", "dynamic"],
) as dag:
    user_list = fetch_users()
    # **Dynamically create tasks using Task Mapping**
    trigger_dag_task = TriggerDagRunOperator.partial(
        task_id="trigger_pipeline",
        trigger_dag_id="email_create_batch_pipeline",
        wait_for_completion=False,
    ).expand(conf=user_list)

    # Define task dependencies
    user_list >> trigger_dag_task
