import csv
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from functools import wraps

import pandas as pd
from airflow.exceptions import AirflowException
from airflow_utils import generate_run_id, save_emails
from auth.gmail_auth import GmailAuthenticator
from dotenv import load_dotenv
from googleapiclient.errors import HttpError
from services.gmail_service import GmailService
from services.storage_service import StorageService
from utils.airflow_utils import (
    authenticate_gmail,
    fetch_emails,
    get_flow,
    get_timestamps,
    handle_http_error,
    retrieve_email_data,
    validate_emails,
)
from utils.db_utils import get_db_session, get_last_read_timestamp

logger = logging.getLogger(__name__)
load_dotenv(os.path.join(os.path.dirname(__file__), "/app/.env"))


def with_email(f):
    """Decorator to handle email from XCom"""

    @wraps(f)
    def wrapper(**context):
        email = context["task_instance"].xcom_pull(task_ids="get_email_for_dag_run")
        if not email:
            raise ValueError("No email found in XCom")
        return f(email=email, **context)

    return wrapper


def check_gmail_oauth2_credentials(**context):
    """
    Check Gmail OAuth2 credentials and refresh if needed.
    """
    logger.info("Starting check_gmail_oauth2_credentials")
    email_address = context["task_instance"].xcom_pull(task_ids="get_email_for_dag_run")
    client_config = get_flow().client_config
    session = get_db_session()

    authenticator = GmailAuthenticator(session)
    credentials = authenticator.authenticate(email_address, client_config)
    if not credentials:
        logging.error("Failed to authenticate Gmail")
        raise Exception("Failed to authenticate Gmail")

    logging.info(f"Authenticated Gmail for {email_address}")

    session.close()
    logger.info("Finished check_gmail_oauth2_credentials")


@with_email
def get_last_read_timestamp_task(email, **context):
    """
    Get the last read timestamp for an email.
    """
    logger.info("Starting get_last_read_timestamp_task")
    try:
        session = get_db_session()
        last_read = get_last_read_timestamp(session, email)
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


@with_email
def choose_processing_path(email, **context) -> str:
    """
    Determines which path to take based on last read timestamp
    Returns task_id of next task to execute
    """
    logger.info("Starting choose_processing_path")

    try:
        session = get_db_session()

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


@with_email
def process_emails_batch(email, **context):
    """Process emails in batch mode."""
    logger.info("Starting process_emails_batch")
    run_id = generate_run_id(context)
    session = get_db_session()

    try:
        credentials = authenticate_gmail(session, email)
        gmail_service = GmailService(credentials)
        start_timestamp, end_timestamp = get_timestamps(session, email)
        messages = fetch_emails(gmail_service, start_timestamp, end_timestamp)
        emails_data = retrieve_email_data(gmail_service, messages)
        validated_emails, num_errors = validate_emails(emails_data)
        file_path = save_emails(email, run_id, validated_emails)

        if file_path is None:
            raise AirflowException("Failed to save emails locally")

        # Create metrics dictionary
        metrics = {
            "total_messages_retrieved": len(messages),
            "emails_processed": len(emails_data),
            "emails_validated": len(validated_emails),
            "validation_errors": num_errors,
            "processing_time": (
                datetime.now(timezone.utc) - start_timestamp
            ).total_seconds(),
            "start_timestamp": start_timestamp.isoformat(),
            "end_timestamp": end_timestamp.isoformat(),
        }

        # Push metrics to XCom
        context["ti"].xcom_push(key="email_processing_metrics", value=metrics)

        logger.info(
            f"Successfully processed {len(validated_emails)} emails with {num_errors} validation errors"
        )

    except HttpError as e:
        handle_http_error(e)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise
    finally:
        session.close()
        logger.info("Finished process_emails_batch")


def process_emails_minibatch(**context):
    """Process emails in mini-batch mode."""
    logger.info("Starting process_emails_minibatch")
    try:
        # Add your processing logic here
        return True
    except Exception as e:
        logger.error(f"Error in process_emails_minibatch: {e}")
        raise
    finally:
        logger.info("Finished process_emails_minibatch")


@with_email
def upload_raw_data_to_gcs(email, **context):
    """Upload raw email data to Google Cloud Storage."""
    logger.info("Starting upload_raw_data_to_gcs")

    try:
        # Get the run_id from XCom
        run_id = context["ti"].xcom_pull(key="run_id")
        if not run_id:
            raise ValueError("No run_id found in XCom")

        # Initialize storage service
        storage_service = StorageService()

        # Get local directory where emails were saved
        local_dir = storage_service.get_emails_dir(email, run_id)
        if not os.path.exists(local_dir):
            raise FileNotFoundError(f"Directory not found: {local_dir}")

        # Upload directory to GCS using StorageService
        bucket_name = os.getenv("BUCKET_NAME")
        if not bucket_name:
            raise ValueError("BUCKET_NAME environment variable is not set")

        logger.info(f"Using GCS bucket: {bucket_name}")
        gcs_prefix = f"emails/{email}/{run_id}/"

        # Use the upload_directory method from StorageService which now returns stats
        upload_stats = storage_service.upload_directory_to_gcs(
            local_dir=local_dir, bucket_name=bucket_name, gcs_prefix=gcs_prefix
        )

        # Log upload statistics
        if isinstance(upload_stats, dict):
            files_uploaded = upload_stats.get("files_uploaded", 0)
            bytes_uploaded = upload_stats.get("bytes_uploaded", 0)
            logger.info(
                f"Successfully uploaded {files_uploaded} files ({bytes_uploaded:,} bytes) to gs://{bucket_name}/{gcs_prefix}"
            )
        else:
            # Backward compatibility if upload_stats is just a count
            files_uploaded = upload_stats
            logger.info(
                f"Successfully uploaded {files_uploaded} files to gs://{bucket_name}/{gcs_prefix}"
            )

        # Store GCS path and stats in XCom for downstream tasks
        gcs_uri = f"gs://{bucket_name}/{gcs_prefix}"
        context["ti"].xcom_push(key="gcs_uri", value=gcs_uri)
        context["ti"].xcom_push(key="upload_stats", value=upload_stats)

        return gcs_uri

    except Exception as e:
        logger.error(f"Error in upload_raw_data_to_gcs: {e}")
        raise
    finally:
        logger.info("Finished upload_raw_data_to_gcs")


def publish_metrics_task(**context):
    """Publish metrics for the pipeline."""
    logger.info("Starting publish_metrics_task")
    try:
        # Add your metrics publishing logic here
        return True
    except Exception as e:
        logger.error(f"Error in publish_metrics_task: {e}")
        raise
    finally:
        logger.info("Finished publish_metrics_task")


def validation_task(**context):
    """Perform data validation for the pipeline."""
    logger.info("Starting data_validation_task")
    try:
        # Add your data validation logic here
        # a = 1 / 0
        return True
    except Exception as e:
        logger.error(f"Error in data_validation_task: {e}")
        raise
    finally:
        logger.info("Finished data_validation_task")


def trigger_preprocessing_pipeline(**context):
    """Trigger the preprocessing pipeline."""
    logger.info("Starting trigger_preprocessing_pipeline")
    try:
        # Add your preprocessing pipeline trigger logic here
        return True
    except Exception as e:
        logger.error(f"Error in trigger_preprocessing_pipeline: {e}")
        raise
    finally:
        logger.info("Finished trigger_preprocessing_pipeline")


def send_failure_email(**context):
    """Send a failure email in case of errors."""
    logger.info("Starting send_failure_email")
    try:
        # Add your failure email logic here
        return True
    except Exception as e:
        logger.error(f"Error in send_failure_email: {e}")
        raise
    finally:
        logger.info("Finished send_failure_email")
