import base64
import csv
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import pandas as pd
from airflow.configuration import conf
from airflow.exceptions import AirflowException
from airflow.utils.email import send_email
from auth.gmail_auth import GmailAuthenticator
from google.cloud import storage
from google_auth_oauthlib.flow import Flow
from googleapiclient.errors import HttpError
from models_postgres import *
from models_pydantic import EmailSchema
from pydantic import ValidationError
from services.storage_service import StorageService
from sqlalchemy import Integer, func
from utils.db_utils import get_db_session, get_last_read_timestamp, update_run_status

logger = logging.getLogger(__name__)


def get_email_for_dag_run(**context):
    """
    Get email from DAG run configuration
    """
    try:
        email = context["dag_run"].conf.get("email_address")
        if not email:
            raise ValueError("No email provided in DAG run configuration")
        context["task_instance"].xcom_push(key="email", value=email)
        return email
    except Exception as e:
        logging.error(f"Error getting email from DAG run: {e}")
        raise


def get_user_id_for_dag_run(**context):
    """
    Get user_id from DAG run configuration
    """
    try:
        user_id = context["dag_run"].conf.get("user_id")
        if not user_id:
            raise ValueError("No user_id provided in DAG run configuration")
        context["task_instance"].xcom_push(key="user_id", value=user_id)
        return user_id
    except Exception as e:
        logging.error(f"Error getting user_id from DAG run: {e}")
        raise


def create_db_session_task(**context):
    """
    Create a database session and store connection details in XCom.
    """
    session = get_db_session()
    # Store the connection URI in XCom
    connection_uri = session.bind.url
    context["task_instance"].xcom_push(
        key="db_connection_uri", value=str(connection_uri)
    )
    update_run_status(
        session,
        context["task_instance"].xcom_pull(key="email"),
        context["task_instance"].xcom_pull(key="user_id"),
        "STARTED",
    )

    # Close the session after use
    session.close()


def get_flow():
    """Return a singleton Flow instance."""
    if not hasattr(get_flow, "flow"):
        logger.info("Creating new Flow instance.")
        get_flow.flow = Flow.from_client_secrets_file(
            os.environ["CREDENTIAL_PATH_FOR_GMAIL_API"],
            scopes=[
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/userinfo.email",
            ],
            redirect_uri=os.environ.get("REDIRECT_URI"),
        )
    else:
        logger.info("Using existing Flow instance.")
    return get_flow.flow


def failure_callback(**context):
    """
    Callback function to handle task failures.
    """
    logger.error(f"Task {context['task'].task_id} failed after retries.")


def generate_run_id():
    run_id = str(uuid.uuid4())
    logger.info(f"Generated run_id: {run_id}")
    return run_id


def authenticate_gmail(session, email):
    authenticator = GmailAuthenticator(session)
    client_config = get_flow().client_config
    credentials = authenticator.authenticate(email, client_config)
    logger.info(f"Authenticated Gmail for {email}")
    return credentials


def get_timestamps(session, user_id, email):
    last_read = get_last_read_timestamp(session, user_id, email)
    start_timestamp = last_read.replace(tzinfo=timezone.utc)
    end_timestamp = datetime.now(timezone.utc)
    logger.info(f"Processing emails from {start_timestamp} to {end_timestamp}")
    return start_timestamp, end_timestamp


def fetch_emails(gmail_service, start_timestamp, end_timestamp):
    messages = gmail_service.list_emails(
        start_timestamp=start_timestamp, end_timestamp=end_timestamp, maxResults=100
    )
    logger.info(f"Retrieved {len(messages)} messages")

    if not messages:
        logger.info("No emails found in the specified time window")
        return []

    return messages


def retrieve_email_data(gmail_service, messages):
    msg_ids = [msg["id"] for msg in messages]
    logger.info(f"Message IDs: {msg_ids}")
    emails_data = gmail_service.get_emails_batch(msg_ids, batch_size=20)
    logger.info(f"Retrieved email data for {len(emails_data)} messages")
    return emails_data


def validate_emails(emails_data):
    validated_emails = []
    num_errors = 0

    for email_data in emails_data.values():
        if email_data is None:
            num_errors += 1
            continue
        try:
            # Clean email addresses
            if isinstance(email_data.get("to"), str):
                email_data["to"] = [
                    addr.strip() for addr in email_data["to"].split(",")
                ]

            validated_email = EmailSchema(**email_data)
            validated_emails.append(validated_email.dict())

            # Log if no content found
            if not validated_email.content:
                logger.warning(f"No content found for email {email_data['message_id']}")

        except ValidationError as e:
            logger.error(
                f"Validation error for email {email_data.get('message_id', 'unknown')}: {e}"
            )
            num_errors += 1

    return validated_emails, num_errors


def save_emails(validated_emails, email, run_id, user_id):
    """Save emails in Parquet format."""
    try:
        # Check if we have valid data to save
        if not validated_emails:
            logger.warning("No validated emails to save")
            return None

        # Save as Parquet files for efficient processing
        parquet_dir = save_emails_as_parquet(email, run_id, validated_emails, user_id)
        if not parquet_dir or not os.path.exists(parquet_dir):
            logger.error(f"Failed to create parquet directory: {parquet_dir}")
            raise Exception("Failed to create parquet directory")

        logger.info(f"Emails saved in Parquet format at {parquet_dir}")

        # Return the parquet directory as the main output
        return parquet_dir

    except Exception as e:
        logger.error(f"Error saving emails: {e}")
        return None


def handle_http_error(e):
    if e.resp.status == 429:
        logger.error("Rate limit exceeded - Airflow will retry")
        raise AirflowException("Rate limit exceeded - Airflow will retry")
    else:
        logger.error(f"HttpError occurred: {e}")
        raise


# Add this function to save emails as Parquet files
def save_emails_as_parquet(email_account, run_id, validated_emails, user_id):
    """Save emails as multiple Parquet files for faster processing."""
    storage_service = StorageService()
    logger.info("Saving emails as Parquet files")

    # Create base directory
    base_dir = storage_service.get_emails_dir(email_account, run_id, user_id)
    logger.info(f"Using directory: {base_dir}")

    # Pre-process data to ensure it's Parquet compatible
    for email_data in validated_emails:
        # Convert any datetime objects to strings
        for key, value in email_data.items():
            if isinstance(value, datetime):
                email_data[key] = value.isoformat()

        # Ensure keys exist and have compatible types
        if "attachments" not in email_data or email_data["attachments"] is None:
            email_data["attachments"] = []

    # Convert to DataFrame for Parquet
    df = pd.DataFrame(validated_emails)

    # Save as a single Parquet file
    parquet_path = os.path.join(base_dir, "emails.parquet")
    df.to_parquet(parquet_path, index=False)
    file_paths = [parquet_path]

    logger.info(f"Saved {len(validated_emails)} emails to {parquet_path}")

    logger.info(
        f"Saved {len(file_paths)} files with {len(validated_emails)} total emails"
    )
    return base_dir


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


def generate_email_content(session, context, type="failure"):
    """Generate email subject and body based on context and notification type."""
    # Get basic information
    task_instance = context.get("task_instance")
    dag_id = task_instance.dag_id
    task_id = task_instance.task_id
    run_id = context["ti"].xcom_pull(key="run_id") or "unknown_run_id"

    # Default content
    subject = f"ALERT: Pipeline {type.capitalize()} - {dag_id}"
    body = f"""
    <h2>Pipeline {type.capitalize()} Notification</h2>
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


# Function to decode Base64 URL-safe encoded strings
def decode_base64_url_safe(encoded_str):
    if pd.isnull(encoded_str):
        return None

    # Replace URL-safe characters
    encoded_str = encoded_str.replace("-", "+").replace("_", "/")

    # Add padding if necessary
    padding = len(encoded_str) % 4
    if padding:
        encoded_str += "=" * (4 - padding)

    try:
        # Decode and return as UTF-8 string
        return base64.b64decode(encoded_str).decode("utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"Error decoding: {e}")
        return None


def monitoring_function(**context):
    logger.info("Running global system monitoring")

    session = get_db_session()
    start_time = datetime.utcnow() - timedelta(days=1)
    ti = context.get("task_instance")

    try:
        # --- MESSAGE METRICS ---
        message_count = session.query(func.count(Message.message_id)).filter(Message.created_at >= start_time).scalar()

        if message_count >= 20:
            toxicity_rate = session.query(func.avg(Message.is_toxic.cast(Integer))).filter(Message.created_at >= start_time).scalar()
            customer_satisfaction = session.query(func.avg(Message.feedback.cast(Integer))).filter(Message.created_at >= start_time).scalar()
            avg_response_time_ms = session.query(func.avg(Message.response_time_ms)).filter(Message.created_at >= start_time).scalar()
        else:
            toxicity_rate = customer_satisfaction = avg_response_time_ms = None

        total_messages = message_count

        # --- EMAIL PROCESSING SUMMARY ---
        processing = session.query(
            func.sum(EmailProcessingSummary.total_emails_processed),
            func.sum(EmailProcessingSummary.total_threads_processed),
            func.sum(EmailProcessingSummary.failed_emails),
            func.sum(EmailProcessingSummary.failed_threads),
        ).filter(EmailProcessingSummary.run_timestamp >= start_time).one()

        # --- EMAIL EMBEDDING SUMMARY ---
        embedding = session.query(
            func.sum(EmailEmbeddingSummary.total_emails_embedded),
            func.sum(EmailEmbeddingSummary.total_threads_embedded),
            func.sum(EmailEmbeddingSummary.failed_emails),
            func.sum(EmailEmbeddingSummary.failed_threads),
        ).filter(EmailEmbeddingSummary.run_timestamp >= start_time).one()

        # --- EMAIL PREPROCESSING SUMMARY ---
        preprocessing = session.query(
            func.sum(EmailPreprocessingSummary.total_emails_processed),
            func.sum(EmailPreprocessingSummary.total_threads_processed),
            func.sum(EmailPreprocessingSummary.successful_emails),
            func.sum(EmailPreprocessingSummary.successful_threads),
            func.sum(EmailPreprocessingSummary.failed_emails),
            func.sum(EmailPreprocessingSummary.failed_threads),
        ).filter(EmailPreprocessingSummary.run_timestamp >= start_time).one()

        # --- METRICS DICT ---
        metrics = {
            "toxicity_rate": toxicity_rate,
            "customer_satisfaction": customer_satisfaction,
            "avg_response_time_ms": avg_response_time_ms,
            "total_messages": total_messages,

            "emails_processed": processing[0] or 0,
            "threads_processed": processing[1] or 0,
            "emails_failed": processing[2] or 0,
            "threads_failed": processing[3] or 0,

            "emails_embedded": embedding[0] or 0,
            "threads_embedded": embedding[1] or 0,
            "embedding_failed_emails": embedding[2] or 0,
            "embedding_failed_threads": embedding[3] or 0,

            "emails_preprocessed": preprocessing[0] or 0,
            "threads_preprocessed": preprocessing[1] or 0,
            "preprocessing_successful_emails": preprocessing[2] or 0,
            "preprocessing_successful_threads": preprocessing[3] or 0,
            "preprocessing_failed_emails": preprocessing[4] or 0,
            "preprocessing_failed_threads": preprocessing[5] or 0,
        }

        logger.info(f"[MONITORING] Daily Metrics:\n{metrics}")

        # --- THRESHOLD CHECKS ---
        alerts = []
        if metrics["toxicity_rate"] is not None and metrics["toxicity_rate"] > 0.10:
            alerts.append(f"toxicity_rate too high: {metrics['toxicity_rate']:.2%}")
        if metrics["customer_satisfaction"] is not None and metrics["customer_satisfaction"] < 0.7:
            alerts.append(f"customer_satisfaction too low: {metrics['customer_satisfaction']:.2f}")
        if metrics["avg_response_time_ms"] is not None and metrics["avg_response_time_ms"] > 3000:
            alerts.append(f"avg_response_time_ms too high: {metrics['avg_response_time_ms']:.2f}ms")
        if metrics["emails_processed"] < 100:
            alerts.append("emails_processed is below threshold (< 100)")
        if metrics["total_messages"] < 100:
            alerts.append("total_messages is below threshold (< 100)")

        embedding_success_rate = metrics["emails_embedded"] / max(metrics["emails_embedded"] + metrics["embedding_failed_emails"], 1)
        if embedding_success_rate < 0.85:
            alerts.append(f"embedding success rate too low: {embedding_success_rate:.2%}")

        if alerts:
            alert_msg = "\n".join(alerts)
            logger.warning(f"[ALERT] Daily System Alert:\n{alert_msg}")
            if ti:
                ti.xcom_push(key="monitoring_alerts", value=alert_msg)
                ti.xcom_push(key="has_alerts", value=True)
            return True  # Return True only when there are alerts
        else:
            logger.info("[MONITORING] No alerts generated")
            if ti:
                ti.xcom_push(key="has_alerts", value=False)
            return False  # Return False when there are no alerts

        # Store metrics in XCom for downstream tasks
        if ti:
            ti.xcom_push(key="monitoring_metrics", value=metrics)

    except Exception as e:
        error_msg = f"[ERROR] Monitoring function failed: {str(e)}"
        logger.exception(error_msg)
        if ti:
            ti.xcom_push(key="monitoring_error", value=error_msg)
            ti.xcom_push(key="has_error", value=True)
        return True  # Return True when there's an error to trigger email notification

    finally:
        session.close()
        logger.info("Finished global monitoring run")


def generate_monitoring_content(**context):
    """
    Generate email subject and body for monitoring alerts.
    """
    task_instance = context.get("task_instance")
    dag_id = task_instance.dag_id
    alert_msg = context["ti"].xcom_pull(key="monitoring_alerts") or "No alerts"
    error_msg = context["ti"].xcom_pull(key="monitoring_error") or "No errors"

    subject = f"ALERT: Monitoring Pipeline - {dag_id}"
    body = f"""
    <h2>Monitoring Pipeline Alert</h2>
    
    <p><strong>DAG:</strong> {dag_id}<br>
    
    <p>{alert_msg}</p>
    
    <p>{error_msg}</p>
    """

    return subject, body