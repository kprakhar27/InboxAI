import logging
import os
import traceback
from datetime import datetime, timedelta, timezone

import pandas as pd
from airflow.exceptions import AirflowException
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from auth.gmail_auth import GmailAuthenticator
from dotenv import load_dotenv
from pydantic import ValidationError
from services.gmail_service import GmailService
from services.storage_service import StorageService
from utils.airflow_utils import (
    authenticate_gmail,
    fetch_emails,
    get_flow,
    get_timestamps,
)
from utils.db_utils import get_db_session, get_last_read_timestamp

logger = logging.getLogger(__name__)
load_dotenv(os.path.join(os.path.dirname(__file__), "/app/.env"))


def check_gmail_oauth2_credentials(**context):
    """
    Check Gmail OAuth2 credentials and refresh if needed.
    """
    logger.info("Starting check_gmail_oauth2_credentials")
    client_config = get_flow().client_config
    session = get_db_session()
    email = context["dag_run"].conf.get("email_address")

    authenticator = GmailAuthenticator(session)
    credentials = authenticator.authenticate(email, client_config)
    if not credentials:
        logging.error("Failed to authenticate Gmail")
        raise Exception("Failed to authenticate Gmail")

    logging.info(f"Authenticated Gmail for {email}")

    session.close()
    logger.info("Finished check_gmail_oauth2_credentials")


def get_last_read_timestamp_task(**context):
    """
    Get the last read timestamp for an email.
    """
    logger.info("Starting get_last_read_timestamp_task")
    try:
        session = get_db_session()
        email = context["dag_run"].conf.get("email_address")
        user_id = context["dag_run"].conf.get("user_id")
        last_read = get_last_read_timestamp(session, user_id, email)
        last_read_str = last_read.strftime("%Y-%m-%d %H:%M:%S.%f %Z")

        end_timestamp = datetime.now(timezone.utc)
        end_timestamp_str = end_timestamp.strftime("%Y-%m-%d %H:%M:%S.%f %Z")

        if last_read is None:
            raise ValueError(f"Failed to get last read timestamp for {email}")

        ts = {"last_read_timestamp": last_read_str, "end_timestamp": end_timestamp_str}

        context["task_instance"].xcom_push(key="timestamps", value=ts)

        logger.info(f"Processing window: {last_read} to {end_timestamp}")

    except Exception as e:
        logger.error(f"Error in get_last_read_timestamp_task: {e}")
        raise
    finally:
        session.close()
        logger.info("Finished get_last_read_timestamp_task")


def choose_processing_path(email, **context) -> str:
    """
    Determines which path to take based on last read timestamp
    Returns task_id of next task to execute
    """
    logger.info("Starting choose_processing_path")

    try:
        session = get_db_session()
        email = context["dag_run"].conf.get("email_address")

        last_read = get_last_read_timestamp(session, email)
        # Add UTC timezone to last_read
        last_read = last_read.replace(tzinfo=timezone.utc)
        # Create end_timestamp with UTC timezone
        end_timestamp = datetime.now(timezone.utc)
        # Format timestamps for logging
        last_read_str = last_read.strftime("%Y-%m-%d %H:%M:%S.%f %Z")
        end_timestamp_str = end_timestamp.strftime("%Y-%m-%d %H:%M:%S.%f %Z")

        # Log the timestamps
        logger.info(f"Last read timestamp: {last_read_str}")
        logger.info(f"End timestamp: {end_timestamp_str}")

        # Calculate the time difference
        time_diff = end_timestamp - last_read

        # Determine the processing path
        if time_diff >= timedelta(hours=6):
            logger.info("Using batch processing")
            return "email_processing.process_emails_batch"
        else:
            logger.info("Less than 6 hours since last read")
            return "email_processing.process_emails_minibatch"

    except Exception as e:
        logger.error(f"Error in branching logic: {e}")
        raise
    finally:
        logger.info("Finished choose_processing_path")


def create_batches(**context):
    """
    Fetch messages IDs and create batches for parallel processing.
    """
    logger.info("Starting create_batches")
    session = get_db_session()
    email = context["dag_run"].conf.get("email_address")
    user_id = context["dag_run"].conf.get("user_id")

    try:
        # Step 1: Setup authentication and services
        credentials = authenticate_gmail(session, email)
        gmail_service = GmailService(credentials)

        # Step 2: Get time range
        start_timestamp, end_timestamp = get_timestamps(session, email)

        # Step 3: Fetch message IDs in time range (reusing fetch_emails)
        message_ids = fetch_emails(gmail_service, start_timestamp, end_timestamp)
        logger.info(f"Retrieved {len(message_ids)} message IDs for time range")

        # Step 4: Create batches of 50 message IDs
        batch_size = 50
        batches = []

        for i in range(0, len(message_ids), batch_size):
            batch = message_ids[i : i + batch_size]
            batch_data = {
                "email": email,
                "user_id": user_id,
                "message_ids": batch,
                "batch_number": i // batch_size + 1,
                "total_batches": (len(message_ids) + batch_size - 1) // batch_size,
                "start_timestamp": start_timestamp.isoformat(),
                "end_timestamp": end_timestamp.isoformat(),
            }
            batches.append(batch_data)

        logger.info(f"Created {len(batches)} batches of {batch_size} messages each")

        # Step 5: Store batch data in XCom
        context["ti"].xcom_push(key="email_batches", value=batches)
        context["ti"].xcom_push(
            key="batch_metadata",
            value={
                "total_messages": len(message_ids),
                "total_batches": len(batches),
                "batch_size": batch_size,
                "start_timestamp": start_timestamp.isoformat(),
                "end_timestamp": end_timestamp.isoformat(),
            },
        )

        return batches

    except Exception as e:
        logger.error(f"Error creating batches: {e}")
        raise
    finally:
        session.close()
        logger.info("Finished create_batches")


def trigger_email_get_for_batches(dag, **context):
    """
    Trigger email_get_pipeline for each batch of email IDs.

    This function pulls batches from the upstream fetch_emails_and_create_batches task
    and triggers a separate DAG run for each batch.
    """
    email = context["dag_run"].conf.get("email_address")
    user_id = context["dag_run"].conf.get("user_id")
    ti = context["task_instance"]

    logger.info(f"Starting trigger_email_get_for_batches for email: {email}")

    # Get the task ID for fetch_emails_and_create_batches including TaskGroup prefix if needed
    task_id = "fetch_emails_and_create_batches"
    task_id_with_group = "email_listing_group.fetch_emails_and_create_batches"

    # Try multiple ways to get batches since the task might be in a TaskGroup
    batches = None

    # First attempt with TaskGroup prefix
    batches = ti.xcom_pull(task_ids=task_id_with_group, key="email_batches")
    logger.info(
        f"Attempted XCom pull from {task_id_with_group}: {'Found' if batches else 'Not found'}"
    )

    if not batches:
        logger.info("No email batches found in XCom - completing successfully")
        return 0

    # Log batch info
    logger.info(f"Found {len(batches)} batches for email {email}")

    # Get metadata the same way
    batch_metadata = None
    batch_metadata = ti.xcom_pull(
        task_ids=task_id_with_group, key="batch_metadata"
    ) or ti.xcom_pull(task_ids=task_id, key="batch_metadata")

    logger.info(f"Triggering preprocessing pipeline for {len(batches)} batches")

    # Track triggered DAGs
    triggered_count = 0

    for batch in batches:
        batch_num = batch["batch_number"]
        total_batches = batch["total_batches"]

        # Create a unique run_id for this batch
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        safe_email = email.replace("@", "_").replace(".", "_")
        run_id = f"email_get_{safe_email}_{batch_num}of{total_batches}_{timestamp}"

        # Prepare configuration for triggered DAG
        conf = {
            "email_address": email,
            "user_id": user_id,
            "batch_number": batch_num,
            "total_batches": total_batches,
            "message_ids": batch["message_ids"],
            "start_timestamp": batch["start_timestamp"],
            "end_timestamp": batch["end_timestamp"],
            "run_id": run_id,
        }

        # Add optional metadata if available
        if batch_metadata:
            conf["batch_metadata"] = batch_metadata

        logger.info(
            f"Triggering email_get_pipeline for batch {batch_num}/{total_batches} with {len(batch['message_ids'])} messages"
        )

        task_id = f"trigger_get_pipeline_{batch_num}"

        # Create and execute the TriggerDagRunOperator
        trigger = TriggerDagRunOperator(
            task_id=task_id,
            trigger_dag_id="email_fetch_pipeline",
            conf=conf,
            reset_dag_run=True,
            wait_for_completion=False,
            dag=dag,
        )

        # Execute the trigger
        try:
            trigger.execute(context=context)
            triggered_count += 1
            logger.info(f"Successfully triggered DAG run with ID: {run_id}")
        except Exception as e:
            logger.error(f"Failed to trigger DAG for batch {batch_num}: {str(e)}")
            logger.error(traceback.format_exc())

    # Store results in XCom
    ti.xcom_push(key="triggered_count", value=triggered_count)

    logger.info(
        f"Successfully triggered {triggered_count}/{len(batches)} preprocessing DAGs"
    )
    return triggered_count
