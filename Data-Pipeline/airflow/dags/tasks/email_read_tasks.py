import csv
import json
import logging
import os
import traceback
from datetime import datetime, timedelta, timezone
from functools import wraps

import pandas as pd
from airflow.configuration import conf
from airflow.exceptions import AirflowException
from airflow.utils.email import send_email
from auth.gmail_auth import GmailAuthenticator
from dotenv import load_dotenv
from googleapiclient.errors import HttpError
from services.gmail_service import GmailService
from services.storage_service import StorageService
from utils.airflow_utils import (
    authenticate_gmail,
    fetch_emails,
    generate_run_id,
    get_flow,
    get_timestamps,
    handle_http_error,
    retrieve_email_data,
    save_emails,
    validate_emails,
)
from utils.db_utils import (
    add_preprocessing_summary,
    get_db_session,
    get_last_read_timestamp,
    update_last_read_timestamp,
)

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

        if num_errors > 0:
            logger.warning(f"Validation errors found for {num_errors} emails")
        elif num_errors == 0:
            logger.info("No validation errors found")

        update_last_read_timestamp(session, email, start_timestamp, end_timestamp)

        # TODO: Add the threads logic here
        # TODO: Add the retry for failed emails logic here

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


@with_email
def process_emails_minibatch(email, **context):
    """Process emails in mini-batch mode."""
    logger.info("Starting process_emails_minibatch")
    run_id = generate_run_id(context)
    session = get_db_session()

    try:
        credentials = authenticate_gmail(session, email)
        gmail_service = GmailService(credentials)
        start_timestamp, end_timestamp = get_timestamps(session, email)

        # Calculate a 6-hour window from end_timestamp to ensure we get responses
        extended_start = end_timestamp - timedelta(hours=6)
        logger.info(
            f"Using extended start time window: {extended_start} (original: {start_timestamp})"
        )

        # Fetch emails using the extended window
        messages = fetch_emails(gmail_service, extended_start, end_timestamp)
        logger.info(f"Retrieved {len(messages)} messages in 6-hour window")

        # Retrieve data for all messages in extended window
        emails_data = retrieve_email_data(gmail_service, messages)

        # Filter emails to only include those within our actual time range
        filtered_emails = []
        for email_data in emails_data:
            # Parse the internal date to compare with our real start_timestamp
            email_date = datetime.fromtimestamp(
                int(email_data.get("internalDate", 0)) / 1000, tz=timezone.utc
            )
            if email_date >= start_timestamp:
                filtered_emails.append(email_data)

        logger.info(
            f"Filtered to {len(filtered_emails)} messages within actual time window"
        )

        # Process the filtered emails
        validated_emails, num_errors = validate_emails(filtered_emails)
        file_path = save_emails(email, run_id, validated_emails)

        if file_path is None:
            raise AirflowException("Failed to save emails locally")

        # Create metrics dictionary
        metrics = {
            "total_messages_retrieved": len(messages),
            "emails_in_timeframe": len(filtered_emails),
            "emails_processed": len(filtered_emails),
            "emails_validated": len(validated_emails),
            "validation_errors": num_errors,
            "processing_time": (
                datetime.now(timezone.utc) - start_timestamp
            ).total_seconds(),
            "start_timestamp": start_timestamp.isoformat(),
            "end_timestamp": end_timestamp.isoformat(),
        }

        if num_errors > 0:
            logger.warning(f"Validation errors found for {num_errors} emails")
        elif num_errors == 0:
            logger.info("No validation errors found")

        update_last_read_timestamp(session, email, start_timestamp, end_timestamp)

        # Push metrics to XCom
        context["ti"].xcom_push(key="email_processing_metrics", value=metrics)
        context["ti"].xcom_push(key="run_id", value=run_id)

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


@with_email
def publish_metrics_task(email, **context):
    """Publish metrics for the pipeline."""
    logger.info("Starting publish_metrics_task")
    try:
        run_id = context["ti"].xcom_pull(key="run_id")
        if not run_id:
            raise ValueError("No run_id found in XCom")

        metrics = context["ti"].xcom_pull(key="email_processing_metrics")
        if not metrics:
            raise ValueError("No metrics found in XCom")

        session = get_db_session()

        # Add your metrics publishing logic here
        logger.info(f"Metrics for run_id {run_id}: {metrics}")
        total_messages = metrics.get("total_messages_retrieved", 0)
        emails_processed = metrics.get("emails_processed", 0)
        emails_validated = metrics.get("emails_validated", 0)
        validation_errors = metrics.get("validation_errors", 0)

        # TODO: Add the threads logic here
        add_preprocessing_summary(
            session,
            run_id,
            email,
            total_messages,
            0,
            emails_validated,
            0,
            validation_errors,
            0,
        )

        session.close()
    except Exception as e:
        logger.error(f"Error in publish_metrics_task: {e}")
        raise
    finally:
        logger.info("Finished publish_metrics_task")


def validation_task(**context):
    """Perform data validation for the pipeline."""
    logger.info("Starting data_validation_task")
    try:
        a = 1 / 0
        metrics = context["ti"].xcom_pull(key="email_processing_metrics")
        if not metrics:
            raise ValueError("No metrics found in XCom")
        upload_stats = context["ti"].xcom_pull(key="upload_stats")
        if not upload_stats:
            raise ValueError("No upload stats found in XCom")

        # Extract validation metrics
        emails_validated = metrics.get("emails_validated", 0)
        validation_errors = metrics.get("validation_errors", 0)
        total_messages = metrics.get("total_messages_retrieved", 0)
        files_uploaded = (
            upload_stats.get("files_uploaded", 0)
            if isinstance(upload_stats, dict)
            else upload_stats
        )

        # Perform validation checks
        validation_results = {
            "metrics_consistency": emails_validated + validation_errors
            == total_messages,
            "upload_completeness": files_uploaded == emails_validated,
            "data_quality": (
                validation_errors / total_messages < 0.1 if total_messages > 0 else True
            ),
        }

        # Log validation results
        for check, result in validation_results.items():
            logger.info(
                f"Validation check '{check}': {'PASSED' if result else 'FAILED'}"
            )

        # Push validation results to XCom
        context["ti"].xcom_push(key="validation_results", value=validation_results)

        # Determine overall validation status
        validation_passed = all(validation_results.values())
        if not validation_passed:
            logger.warning("Data validation failed. See logs for details.")
            raise ValueError("Data validation failed")
        else:
            logger.info("All data validation checks passed")

        return validation_passed
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
    """Send a basic failure email notification with run ID."""
    logger.info("Starting send_failure_email")
    try:
        # Get run_id and task information from context
        run_id = context["ti"].xcom_pull(key="run_id") or "unknown_run_id"
        task_instance = context.get("task_instance")
        dag_id = task_instance.dag_id
        task_id = task_instance.task_id

        # Simple subject and body
        subject = f"ALERT: Email Processing Failed - Run ID: {run_id}"
        body = f"""
        <h2>Email Processing Pipeline Failure</h2>
        
        <p><strong>Run ID:</strong> {run_id}<br>
        <strong>DAG:</strong> {dag_id}<br>
        <strong>Task:</strong> {task_id}</p>
        
        <p>The email processing pipeline has encountered an error.</p>
        <p>Please check the Airflow logs for more details.</p>
        """

        # Get recipients from environment (could be either ALERT_EMAIL or AIRFLOW_ALERT_EMAIL)
        recipients = os.getenv("ALERT_EMAIL") or os.getenv(
            "AIRFLOW_ALERT_EMAIL", "pc612001@gmail.com"
        ).split(",")
        if isinstance(recipients, str):
            recipients = recipients.split(",")

        # Debug log about email configuration
        logger.info(f"Email recipients: {', '.join(recipients)}")

        smtp_host = conf.get("smtp", "smtp_host", fallback=None)
        smtp_port = conf.get("smtp", "smtp_port", fallback=None)

        if smtp_host and smtp_port:
            logger.info(f"Sending email using SMTP server: {smtp_host}:{smtp_port}")
        else:
            # Try to get from environment variables directly
            smtp_host = os.getenv("SMTP_HOST") or os.getenv("AIRFLOW__SMTP__SMTP_HOST")
            smtp_port = os.getenv("SMTP_PORT") or os.getenv("AIRFLOW__SMTP__SMTP_PORT")
            logger.info(
                f"Using environment variables for SMTP: {smtp_host}:{smtp_port}"
            )

        send_email(
            to=recipients,
            subject=subject,
            html_content=body,
        )

        logger.info(f"Sent failure notification for run_id {run_id}")
        return True
    except Exception as e:
        logger.error(f"Error sending failure email: {str(e)}")
        return False
    finally:
        logger.info("Finished send_failure_email")
