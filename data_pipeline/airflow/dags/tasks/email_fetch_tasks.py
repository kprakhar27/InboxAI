import logging
import os
import traceback
from datetime import datetime, timedelta, timezone
from functools import wraps

from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from dotenv import load_dotenv
from pydantic import ValidationError
from services.gmail_service import GmailService
from services.storage_service import StorageService
from utils.airflow_utils import (
    authenticate_gmail,
    generate_email_content,
    generate_run_id,
    retrieve_email_data,
    save_emails,
    send_notification_email,
    validate_emails,
)
from utils.db_utils import (
    add_preprocessing_summary,
    get_db_session,
    update_last_read_timestamp,
)

logger = logging.getLogger(__name__)
load_dotenv(os.path.join(os.path.dirname(__file__), "/app/.env"))


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
        user_id = conf.get("user_id")

        # Extract timestamps
        start_timestamp = conf.get("start_timestamp")
        end_timestamp = conf.get("end_timestamp")

        # Create structured batch data
        batch_data = {
            "email": email,
            "user_id": user_id,
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
    """
    Process a batch of emails from the batch_data XCom.
    Validates emails using Pydantic models and saves them to storage.
    """
    logger.info("Starting process_emails_batch")
    session = None

    try:
        # Get batch data from XCom
        ti = context["task_instance"]
        batch_data = ti.xcom_pull(key="batch_data")

        if not batch_data or not isinstance(batch_data, dict):
            raise ValueError("Invalid or missing batch data from XCom")

        # Extract data from batch
        email_address = batch_data.get("email")
        user_id = batch_data.get("user_id")
        message_ids = batch_data.get("message_ids", [])
        batch_number = batch_data.get("batch_number")
        total_batches = batch_data.get("total_batches")

        logger.info(
            f"Processing batch {batch_number}/{total_batches} with {len(message_ids)} messages for {email_address}"
        )

        # Generate a run ID for this batch processing
        run_id = generate_run_id()
        ti.xcom_push(key="run_id", value=run_id)

        # Set up services
        session = get_db_session()
        credentials = authenticate_gmail(session, email_address)
        gmail_service = GmailService(credentials)

        # Retrieve email data
        emails_data = retrieve_email_data(gmail_service, message_ids)
        logger.info(f"Retrieved {len(emails_data)} emails")

        # Validate emails using Pydantic models
        valid_emails, validation_errors = validate_emails(emails_data)
        logger.info(
            f"Validated emails: {len(valid_emails)} valid, {validation_errors} errors"
        )

        # Save validated emails to storage
        saved_count = save_emails(valid_emails, email_address, run_id, user_id)
        logger.info(f"Saved {saved_count} emails to storage")

        # Collect metrics
        metrics = {
            "total_messages_retrieved": len(message_ids),
            "emails_processed": len(emails_data),
            "emails_validated": len(valid_emails),
            "validation_errors": validation_errors,
            "batch_number": batch_number,
            "total_batches": total_batches,
        }

        # Update last read timestamp only if this is the last batch
        if batch_number == total_batches:
            end_timestamp = datetime.fromisoformat(batch_data.get("end_timestamp"))
            start_timestamp = datetime.fromisoformat(batch_data.get("start_timestamp"))
            update_last_read_timestamp(
                session, email_address, start_timestamp, end_timestamp
            )
            logger.info(f"Updated last read timestamp to {end_timestamp}")

        # Push metrics to XCom
        ti.xcom_push(key="email_processing_metrics", value=metrics)

        return metrics

    except Exception as e:
        logger.error(f"Error in process_emails_batch: {e}")
        logger.error(traceback.format_exc())
        raise
    finally:
        if session:
            session.close()
        logger.info("Finished process_emails_batch")


def upload_raw_data_to_gcs(**context):
    email = context["dag_run"].conf.get("email_address")
    user_id = context["dag_run"].conf.get("user_id")

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
        local_dir = storage_service.get_emails_dir(email, run_id, user_id)
        if not os.path.exists(local_dir):
            raise FileNotFoundError(f"Directory not found: {local_dir}")

        # Upload directory to GCS using StorageService
        bucket_name = os.getenv("BUCKET_NAME")
        if not bucket_name:
            raise ValueError("BUCKET_NAME environment variable is not set")

        logger.info(f"Using GCS bucket: {bucket_name}")
        gcs_prefix = f"raw/{user_id}/{run_id}/{email}"

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
    email = context["dag_run"].conf.get("email_address")
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
            upload_stats.get("successful", 0)
            if isinstance(upload_stats, dict)
            else upload_stats
        )

        logging.info(files_uploaded)

        # Perform validation checks
        validation_results = {
            "metrics_consistency": emails_validated + validation_errors
            == total_messages,
            "upload_completeness": files_uploaded == 1,
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
        gcs_uri = context["ti"].xcom_pull(key="gcs_uri")
        conf = {"gcs_uri": gcs_uri}
        trigger_task = TriggerDagRunOperator(
            task_id="trigger_embedding_dag",
            trigger_dag_id="email_preprocessing_pipeline",
            conf=conf,
            reset_dag_run=True,
            wait_for_completion=False,
        )
        trigger_task.execute(context=context)
    except Exception as e:
        logger.error(f"Error in trigger_preprocessing_pipeline: {e}")
        raise
    finally:
        logger.info("Finished trigger_preprocessing_pipeline")


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

def send_success_email(**context):
    """Send a success email notification."""
    logger.info("Starting send_success_email")
    try:
        subject, body = generate_email_content(context, type="success")
        result = send_notification_email(subject, body)

        return result
    except Exception as e:
        logger.error(f"Error in send_success_email: {str(e)}")
        return False
    finally:
        logger.info("Finished send_success_email")
