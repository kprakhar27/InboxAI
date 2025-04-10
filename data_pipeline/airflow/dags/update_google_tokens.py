import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from google.auth.transport.requests import Request
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


def refresh_google_tokens(**context):
    """
    Refresh Google OAuth tokens that are about to expire.
    Updates the tokens in the database with new access tokens and expiry times.
    """
    try:
        logger.info("Starting Google token refresh process")
        session = get_db_session()

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
                    client_id=context["var"].value.get("GOOGLE_CLIENT_ID"),
                    client_secret=context["var"].value.get("GOOGLE_CLIENT_SECRET"),
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
    start_date=datetime(2024, 1, 1),
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
    start >> refresh_tokens >> send_failure_notification

    logger.info("Google Token Update Pipeline DAG fully initialized")
