import json
import logging
import os
from datetime import datetime, timedelta

import google.cloud.logging
from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from google.auth.transport.requests import Request
from google.cloud.logging.handlers import CloudLoggingHandler
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from models_postgres import GoogleToken
from tasks.email_fetch_tasks import send_failure_email
from utils.airflow_utils import failure_callback
from utils.db_utils import get_db_session
from utils.gcp_logging_utils import setup_gcp_logging

# Initialize logger
logger = setup_gcp_logging("update_google_tokens")
logger.info("Initialized logger for update_google_tokens")

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": failure_callback,
}


def test_gcp_logging(**context):
    """Test task to verify GCP logging setup."""
    try:
        import google.cloud.logging
        from google.cloud.logging.handlers import CloudLoggingHandler

        # Print environment info
        logger.info(f"Testing GCP logging setup...")
        logger.info(
            f"GOOGLE_APPLICATION_CREDENTIALS = {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}"
        )

        # Test direct client initialization
        credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path
        )
        client = google.cloud.logging.Client(credentials=credentials)
        logger.info(f"GCP logging client initialized successfully")
        logger.info(f"Using GCP project: {client.project}")

        # Test custom handler
        handler = CloudLoggingHandler(client)
        test_logger = logging.getLogger("test_logger")
        test_logger.setLevel(logging.INFO)
        test_logger.addHandler(handler)

        # Send test messages
        test_logger.info("TEST MESSAGE 1 - Direct from test logger")
        logger.info("TEST MESSAGE 2 - From DAG logger")

        return "GCP logging test completed successfully"

    except Exception as e:
        logger.error(f"GCP logging test failed: {str(e)}")
        raise


def get_oauth_credentials():
    """Load OAuth credentials from JSON file."""
    try:
        cred_path = os.environ.get("CREDENTIAL_PATH_FOR_GMAIL_API", "credentials.json")
        with open(cred_path) as f:
            creds = json.load(f)
        return creds["installed"]["client_id"], creds["installed"]["client_secret"]
    except Exception as e:
        logger.error(f"Error loading OAuth credentials: {str(e)}")
        raise


def refresh_google_tokens(**context):
    """
    Refresh Google OAuth tokens that are about to expire.
    Updates the tokens in the database with new access tokens and expiry times.
    """
    try:
        logger.info("Starting Google token refresh process")
        session = get_db_session()

        # Get Google OAuth credentials from credentials.json
        client_id, client_secret = get_oauth_credentials()

        # Get all tokens that will expire in the next hour
        expiry_threshold = datetime.utcnow() + timedelta(hours=1)
        google_tokens = (
            session.query(GoogleToken)
            .filter(GoogleToken.expires_at <= expiry_threshold)
            .all()
        )

        logger.info(f"Found {len(google_tokens)} tokens to refresh")

        for token in google_tokens:
            try:
                # Create credentials object
                creds = Credentials(
                    token=token.access_token,
                    refresh_token=token.refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=client_id,
                    client_secret=client_secret,
                )

                if not creds.valid or creds.expired:
                    logger.info(f"Refreshing token for email: {token.email}")
                    creds.refresh(Request())

                    # Update token in database
                    token.access_token = creds.token
                    token.expires_at = datetime.utcnow() + timedelta(
                        seconds=creds.expiry.timestamp() - datetime.utcnow().timestamp()
                    )
                    logger.info(
                        f"Successfully refreshed token for email: {token.email}"
                    )

            except Exception as e:
                logger.error(
                    f"Error refreshing token for email {token.email}: {str(e)}"
                )
                continue

        # Commit all changes
        session.commit()
        logger.info("Successfully completed token refresh process")

    except Exception as e:
        logger.error(f"Database error in token refresh: {str(e)}")
        if session:
            session.rollback()
        raise

    finally:
        if session:
            session.close()


with DAG(
    dag_id="update_google_tokens",
    default_args=default_args,
    description="Updates Google OAuth tokens before expiry",
    schedule_interval="@hourly",
    start_date=datetime.now() - timedelta(days=1),
    catchup=False,
    max_active_runs=1,
    tags=["google", "oauth", "maintenance"],
) as dag:
    """
    ### Google Token Update Pipeline

    This DAG performs the following steps:
    1. Identifies tokens that will expire in the next hour
    2. Refreshes those tokens using the refresh token
    3. Updates the database with new access tokens and expiry times
    4. Sends notification on failure
    """
    logger.info("Initializing Google Token Update Pipeline DAG")

    # Start task
    start = EmptyOperator(
        task_id="start",
        doc="Start of the token refresh pipeline.",
    )

    # Test GCP logging task
    test_logging = PythonOperator(
        task_id="test_gcp_logging",
        python_callable=test_gcp_logging,
        provide_context=True,
        doc="Tests GCP logging configuration",
    )

    # Refresh tokens task
    refresh_tokens = PythonOperator(
        task_id="refresh_google_tokens",
        python_callable=refresh_google_tokens,
        provide_context=True,
        doc="Refreshes Google OAuth tokens that are about to expire.",
    )

    # Failure notification task
    send_failure_notification = PythonOperator(
        task_id="send_failure_notification",
        python_callable=send_failure_email,
        provide_context=True,
        trigger_rule="one_failed",
        doc="Sends notification email if token refresh fails.",
    )

    # Define task dependencies
    start >> test_logging >> refresh_tokens >> send_failure_notification

    logger.info("Google Token Update Pipeline DAG fully initialized")
