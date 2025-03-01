import csv
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import pandas as pd
from airflow.exceptions import AirflowException
from auth.gmail_auth import GmailAuthenticator
from google.cloud import storage
from google_auth_oauthlib.flow import Flow
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


def generate_run_id(context):
    run_id = str(uuid.uuid4())
    context["ti"].xcom_push(key="run_id", value=run_id)
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


def save_emails(email, run_id, validated_emails):
    """Save emails in Parquet format (with JSON backup)."""
    storage_service = StorageService()

    try:
        # Check if we have valid data to save
        if not validated_emails:
            logger.warning("No validated emails to save")
            return None

        # Save as Parquet files for efficient processing
        parquet_dir = save_emails_as_parquet(email, run_id, validated_emails)
        if not parquet_dir or not os.path.exists(parquet_dir):
            logger.error(f"Failed to create parquet directory: {parquet_dir}")
            raise Exception("Failed to create parquet directory")

        # Also save as JSON for backward compatibility
        logger.info("Also saving emails in JSON format for compatibility")
        json_path = storage_service.save_emails_locally(email, run_id, validated_emails)
        if not json_path or not os.path.exists(os.path.dirname(json_path)):
            logger.error(f"Failed to create JSON file: {json_path}")
            raise Exception("Failed to create JSON file")

        logger.info(f"Emails saved in Parquet format at {parquet_dir}")
        logger.info(f"Emails saved in JSON format at {json_path}")

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
def save_emails_as_parquet(email_account, run_id, validated_emails, batch_size=50):
    """Save emails as multiple Parquet files for faster processing."""
    storage_service = StorageService()
    logger.info("Saving emails as Parquet files")

    # Create base directory
    base_dir = storage_service.get_emails_dir(email_account, run_id)
    logger.info(f"Using directory: {base_dir}")

    # Create metadata file with summary
    metadata = {
        "email_account": email_account,
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_emails": len(validated_emails),
        "batch_size": batch_size,
        "num_batches": (len(validated_emails) + batch_size - 1) // batch_size,
    }

    with open(os.path.join(base_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    file_paths = []

    # Pre-process data to ensure it's Parquet compatible
    for email_data in validated_emails:
        # Convert any datetime objects to strings
        for key, value in email_data.items():
            if isinstance(value, datetime):
                email_data[key] = value.isoformat()

        # Ensure keys exist and have compatible types
        if "attachments" not in email_data or email_data["attachments"] is None:
            email_data["attachments"] = []

    # Process in batches
    for i in range(0, len(validated_emails), batch_size):
        batch = validated_emails[i : i + batch_size]
        batch_num = i // batch_size + 1

        # Convert to DataFrame for Parquet
        df = pd.DataFrame(batch)

        # Save as Parquet file
        parquet_path = os.path.join(base_dir, f"emails_batch_{batch_num:05d}.parquet")
        df.to_parquet(parquet_path, index=False)
        file_paths.append(parquet_path)

        logger.info(
            f"Saved batch {batch_num} with {len(batch)} emails to {parquet_path}"
        )

    # Save email index for quick lookup
    index_data = []
    for i, email_data in enumerate(validated_emails):
        index_data.append(
            {
                "message_id": email_data["message_id"],
                "from_email": email_data["from_email"],
                "subject": email_data["subject"],
                "date": email_data["date"],
                "batch_num": (i // batch_size) + 1,
            }
        )

    index_df = pd.DataFrame(index_data)
    index_path = os.path.join(base_dir, "email_index.parquet")
    index_df.to_parquet(index_path, index=False)

    logger.info(
        f"Saved {len(file_paths)} files with {len(validated_emails)} total emails"
    )
    return base_dir
