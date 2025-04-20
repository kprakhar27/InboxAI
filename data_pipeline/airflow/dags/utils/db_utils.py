import logging
import os
from datetime import datetime, timedelta, timezone

from airflow.providers.postgres.hooks.postgres import PostgresHook
from dotenv import load_dotenv
from dags.models_postgres import (
    EmailEmbeddingSummary,
    EmailPreprocessingSummary,
    EmailProcessingSummary,
    EmailReadTracker,
    EmailReadyForProcessing,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

load_dotenv(os.path.join(os.path.dirname(__file__), "/app/.env"))

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")


def get_db_session():
    db_uri = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    print(db_uri)
    if not db_uri:
        logger.error("Database URI is not set. Please check environment variables.")
        raise ValueError("DATABASE_URL environment variable not set")
    try:
        engine = create_engine(db_uri)
        Session = sessionmaker(bind=engine)
        logger.info("Database session created successfully.")
        return Session()
    except Exception as e:
        logger.error(f"Error creating database session: {e}")
        raise


def get_last_read_timestamp(session, user_id, email):
    """Fetch the last read timestamp for an email."""
    try:
        logger.info(
            f"Fetching last read timestamp for email: {email} and user_id: {user_id}"
        )
        tracker = (
            session.query(EmailReadTracker)
            .filter_by(email=email, user_id=user_id)
            .first()
        )
        if tracker:
            logger.info(f"Found last read timestamp: {tracker.last_read_at}")
            return tracker.last_read_at
        else:
            # Default to 6 months ago if no record exists
            default_timestamp = datetime.now(timezone.utc) - timedelta(days=30)
            logger.info(
                f"No record found. Returning default timestamp: {default_timestamp}"
            )
            return default_timestamp
    except Exception as e:
        logger.error(
            f"Error fetching last read timestamp for email {email} and user_id {user_id}: {e}"
        )
        return None


def update_last_read_timestamp(session, email, second_last, timestamp, user_id):
    """Update the last read timestamp for an email."""
    try:
        logger.info(
            f"Updating last read timestamp for email: {email} and user_id: {user_id} to {timestamp}"
        )
        tracker = (
            session.query(EmailReadTracker)
            .filter_by(email=email, user_id=user_id)
            .first()
        )
        if tracker:
            tracker.second_last_read_at = second_last
            tracker.last_read_at = timestamp
            logger.info("Updated existing record.")
        else:
            tracker = EmailReadTracker(
                email=email, last_read_at=timestamp, user_id=user_id
            )
            session.add(tracker)
            logger.info("Created new record.")
        session.commit()
        logger.info("Database commit successful.")
    except Exception as e:
        session.rollback()
        logger.error(
            f"Error updating last read timestamp for email {email} and user_id {user_id}: {e}"
        )


def update_run_status(session, email, user_id, status):
    """Update the run status for an email."""
    logger.info(f"Updating run status for email: {email} to {status}")
    # Check if the email is already in the email_run_status table
    # Update email_run_status table
    query = f"""
            INSERT INTO email_run_status (user_id, email, run_status)
            VALUES (:user_id, :email, '{status}')
            ON CONFLICT (user_id) 
            DO UPDATE SET run_status = '{status}', email = :email
        """

    session.execute(query, {"user_id": user_id, "email": email})
    session.commit()
    logger.info("Run status updated successfully.")


def add_unique_timestamps(session, timestamp_email_map):
    """Add unique timestamps and email addresses to the EmailReadyForProcessing table."""
    try:
        logger.info("Starting to add unique timestamps and email addresses.")
        for timestamp, email_data in timestamp_email_map.items():
            for email_address, item_type in email_data:
                record = EmailReadyForProcessing(
                    raw_to_gcs_timestamp=datetime.strptime(timestamp, "%m%d%Yat%H%M"),
                    email=email_address,
                    item_type=item_type,
                    status="unprocessed",
                )
                session.add(record)
        session.commit()
        logger.info("All records added successfully. Database commit successful.")
    except Exception as e:
        session.rollback()
        logger.error(f"Error adding unique timestamps and email addresses: {e}")


def fetch_ready_for_processing(session, email=None):
    """Fetch records that are ready for preprocessing. Optionally filter by email."""
    try:
        query = session.query(EmailReadyForProcessing).filter_by(status="unprocessed")
        if email:
            query = query.filter_by(email=email)
        results = query.order_by(EmailReadyForProcessing.email).all()
        return results
    except Exception as e:
        logger.error(f"Error fetching ready for processing records: {e}")
        return []


def update_processing_status(session, run_id, status):
    """Update the processing status of a record."""
    try:
        record = session.query(EmailReadyForProcessing).filter_by(run_id=run_id).first()
        if record:
            record.status = status
            record.updated_at = datetime.now()
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating processing status for run_id {run_id}: {e}")
        return False


def add_preprocessing_summary(
    session,
    run_id,
    user_id,
    email,
    total_emails_processed,
    total_threads_processed,
    successful_emails,
    successful_threads,
    failed_emails,
    failed_threads,
):
    """Add a preprocessing summary record to the database."""
    try:
        summary = EmailPreprocessingSummary(
            run_id=run_id,
            user_id=user_id,
            email=email,
            total_emails_processed=total_emails_processed,
            total_threads_processed=total_threads_processed,
            successful_emails=successful_emails,
            successful_threads=successful_threads,
            failed_emails=failed_emails,
            failed_threads=failed_threads,
        )
        session.add(summary)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error adding preprocessing summary for email {email}: {e}")
        return False


def add_processing_summary(
    session, user_id, email, total_emails, total_threads, failed_emails, failed_threads
):
    """
    Add a processing summary record to the EmailProcessingSummary table.
    """
    try:
        logger.info(f"Adding processing summary for email: {email}")
        summary = EmailProcessingSummary(
            user_id=user_id,
            email=email,
            total_emails_processed=total_emails,
            total_threads_processed=total_threads,
            failed_emails=failed_emails,
            failed_threads=failed_threads,
        )
        session.add(summary)
        session.commit()
        logger.info("Processing summary added successfully")
        return True

    except Exception as e:
        session.rollback()
        logger.error(f"Error adding processing summary for email {email}: {str(e)}")
        return False


def add_embedding_summary(
    session,
    user_id,
    email,
    total_emails_embedded,
    total_threads_embedded,
    failed_emails,
    failed_threads,
):
    """
    Add an embedding summary record to the EmailEmbeddingSummary table.
    """

    try:
        logger.info(f"Adding embedding summary for email: {email}")
        summary = EmailEmbeddingSummary(
            user_id=user_id,
            email=email,
            total_emails_embedded=total_emails_embedded,
            total_threads_embedded=total_threads_embedded,
            failed_emails=failed_emails,
            failed_threads=failed_threads,
        )
        session.add(summary)
        session.commit()
        logger.info("Embedding summary added successfully")
        return True

    except Exception as e:
        session.rollback()
        logger.error(f"Error adding embedding summary for email {email}: {str(e)}")
        return False
