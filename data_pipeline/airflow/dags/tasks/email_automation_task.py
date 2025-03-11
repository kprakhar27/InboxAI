import logging
import os
import traceback
from datetime import datetime, timedelta, timezone
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from dotenv import load_dotenv
from utils.db_utils import get_db_session
import uuid
logger = logging.getLogger(__name__)
load_dotenv(os.path.join(os.path.dirname(__file__), "/app/.env"))


def automate_data_pipeline(**context):
    try:
        logger.info("connecting to Database....")
        session=get_db_session()
        results=session.execute("select * from google_tokens")
        users=[[str(result[1]),result[2]] for result in results]
        logger.info("Retrived users from DB")
        session.close()
        logger.info("Initialzing Trigger for data pipeline")
        for user in users:
            trigger_task = TriggerDagRunOperator(
                task_id=f"trigger_data_pipeline_{user[0]}",
                trigger_dag_id="email_create_batch_pipeline",
                conf={
                "user_id": user[0],
                "email_address": user[1]
                },
                reset_dag_run=True,
                wait_for_completion=False,
            )
            trigger_task.execute(context=context)
            logger.info("Triggered successfully")
    except Exception as e:
        logger.error(f"Error in triggering data pipeline: {e}")
        raise
