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
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
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
        logger.error("No email batches found in XCom")
        raise ValueError("No email batches found to process")

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
            trigger_dag_id="email_get_pipeline",
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


def get_batch_data_from_trigger(**context):
    """
    Extract batch data from the triggering DAG run.

    This function:
    1. Gets the batch information from the DAG run configuration
    2. Validates required fields
    3. Returns structured batch data for downstream tasks
    """
    try:
        ti = context["task_instance"]
        dag_run = context["dag_run"]

        if not dag_run or not dag_run.conf:
            raise ValueError("No configuration found in DAG run")

        conf = dag_run.conf

        # Extract required fields with validation
        required_fields = [
            "email_address",
            "message_ids",
            "batch_number",
            "total_batches",
        ]
        for field in required_fields:
            if field not in conf:
                raise ValueError(
                    f"Required field '{field}' missing from DAG run configuration"
                )

        # Extract data
        email = conf["email_address"]
        message_ids = conf["message_ids"]
        batch_number = conf["batch_number"]
        total_batches = conf["total_batches"]

        # Extract timestamps
        start_timestamp = conf.get("start_timestamp")
        end_timestamp = conf.get("end_timestamp")

        # Create structured batch data
        batch_data = {
            "email": email,
            "message_ids": message_ids,
            "batch_number": batch_number,
            "total_batches": total_batches,
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
            "parent_run_id": conf.get("parent_run_id"),
        }

        # Store in XCom for downstream tasks
        ti.xcom_push(key="batch_data", value=batch_data)

        logger.info(
            f"Processing batch {batch_number}/{total_batches} with {len(message_ids)} messages for {email}"
        )
        return batch_data

    except Exception as e:
        logger.error(f"Error extracting batch data: {str(e)}")
        raise


def process_emails_batch(**context):
    """Process emails in batch mode."""
    logger.info("Starting process_emails_batch")
    run_id = generate_run_id(context)
    session = get_db_session()
    email = 1

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


def process_emails_minibatch(**context):
    email = 1
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


def upload_raw_data_to_gcs(**context):
    email = 1
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
    email = 1
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


def get_email_recipients():
    """Get the list of email recipients from environment variables."""
    recipients = os.getenv("ALERT_EMAIL") or os.getenv(
        "AIRFLOW_ALERT_EMAIL", "pc612001@gmail.com"
    ).split(",")
    if isinstance(recipients, str):
        recipients = recipients.split(",")
    return recipients


def get_smtp_config():
    """Get SMTP configuration from Airflow config or environment variables."""
    smtp_host = conf.get("smtp", "smtp_host", fallback=None)
    smtp_port = conf.get("smtp", "smtp_port", fallback=None)

    if not smtp_host or not smtp_port:
        # Fallback to environment variables
        smtp_host = os.getenv("SMTP_HOST") or os.getenv("AIRFLOW__SMTP__SMTP_HOST")
        smtp_port = os.getenv("SMTP_PORT") or os.getenv("AIRFLOW__SMTP__SMTP_PORT")

    return smtp_host, smtp_port


def generate_email_content(context, type="failure"):
    """Generate email subject and body based on context and notification type."""
    # Get basic information
    task_instance = context.get("task_instance")
    dag_id = task_instance.dag_id
    task_id = task_instance.task_id
    run_id = context["ti"].xcom_pull(key="run_id") or "unknown_run_id"

    # Default content
    subject = f"ALERT: Pipeline {type.capitalize()} - {dag_id} - Run ID: {run_id}"
    body = f"""
    <h2>Pipeline {type.capitalize()} Notification</h2>
    
    <p><strong>Run ID:</strong> {run_id}<br>
    <strong>DAG:</strong> {dag_id}<br>
    <strong>Task:</strong> {task_id}</p>
    
    <p>The pipeline has {type}d.</p>
    <p>Please check the Airflow logs for more details.</p>
    """

    # Customize based on DAG ID
    if "email" in dag_id:
        subject = f"ALERT: Email Processing {type.capitalize()} - Run ID: {run_id}"
        body = f"""
        <h2>Email Processing Pipeline {type.capitalize()}</h2>
        
        <p><strong>Run ID:</strong> {run_id}<br>
        <strong>DAG:</strong> {dag_id}<br>
        <strong>Task:</strong> {task_id}</p>
        
        <p>The email processing pipeline has {type}d.</p>
        <p>Please check the Airflow logs for more details.</p>
        """
    elif "preprocessing" in dag_id:
        subject = (
            f"ALERT: Preprocessing Pipeline {type.capitalize()} - Run ID: {run_id}"
        )
        body = f"""
        <h2>Data Preprocessing Pipeline {type.capitalize()}</h2>
        
        <p><strong>Run ID:</strong> {run_id}<br>
        <strong>DAG:</strong> {dag_id}<br>
        <strong>Task:</strong> {task_id}</p>
        
        <p>The data preprocessing pipeline has {type}d.</p>
        <p>Please check the Airflow logs for more details.</p>
        """

    return subject, body


def send_notification_email(subject, body, recipients=None):
    """Send an email notification with the given subject and body."""
    if recipients is None:
        recipients = get_email_recipients()

    logger.info(f"Email recipients: {', '.join(recipients)}")

    smtp_host, smtp_port = get_smtp_config()
    logger.info(f"SMTP configuration: {smtp_host}:{smtp_port}")

    try:
        send_email(
            to=recipients,
            subject=subject,
            html_content=body,
        )
        return True
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return False


def send_failure_email(**context):
    """Send a failure email notification."""
    logger.info("Starting send_failure_email")
    try:
        subject, body = generate_email_content(context, type="failure")
        result = send_notification_email(subject, body)

        run_id = context["ti"].xcom_pull(key="run_id") or "unknown_run_id"
        if result:
            logger.info(f"Sent failure notification for run_id {run_id}")

        return result
    except Exception as e:
        logger.error(f"Error in send_failure_email: {str(e)}")
        return False
    finally:
        logger.info("Finished send_failure_email")
