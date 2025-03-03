import base64
import csv
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import pandas as pd
from airflow.configuration import conf
from airflow.exceptions import AirflowException
from airflow.utils.email import send_email
from auth.gmail_auth import GmailAuthenticator
from google.cloud import storage
from google_auth_oauthlib.flow import Flow
from googleapiclient.errors import HttpError
from models_pydantic import EmailSchema
from pydantic import ValidationError
from services.storage_service import StorageService
from utils.db_utils import get_db_session, get_last_read_timestamp

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


def get_timestamps(session, email):
    last_read = get_last_read_timestamp(session, email)
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


def generate_email_content(context, type="failure"):
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
