# email_module/utils/db_handler.py
import logging
import os
from datetime import datetime, timedelta, timezone
from os.path import dirname, join

from app.models import (
    EmailPreprocessingSummary,
    EmailProcessingSummary,
    EmailReadTracker,
    EmailReadyForProcessing,
)
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

dotenv_path = join(dirname(__file__), ".env")
load_dotenv(dotenv_path)

DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT")
DB_NAME = os.environ.get("DB_NAME")

# Use the same database URL as your Flask app
DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create a SQLAlchemy engine and session factory
engine = create_engine(DATABASE_URI)
Session = sessionmaker(bind=engine)


def get_session():
    """Create and return a new database session."""
    logger.info("Creating a new database session.")
    return Session()


def get_last_read_timestamp(session, email):
    """Fetch the last read timestamp for an email."""
    try:
        logger.info(f"Fetching last read timestamp for email: {email}")
        tracker = session.query(EmailReadTracker).filter_by(email=email).first()
        if tracker:
            logger.info(f"Found last read timestamp: {tracker.last_read_at}")
            return tracker.last_read_at
        else:
            # Default to 6 months ago if no record exists
            default_timestamp = datetime.now(timezone.utc) - timedelta(days=180)
            logger.info(
                f"No record found. Returning default timestamp: {default_timestamp}"
            )
            return default_timestamp
    except Exception as e:
        logger.error(f"Error fetching last read timestamp for email {email}: {e}")
        return None


def update_last_read_timestamp(session, email, second_last, timestamp):
    """Update the last read timestamp for an email."""
    try:
        logger.info(f"Updating last read timestamp for email: {email} to {timestamp}")
        tracker = session.query(EmailReadTracker).filter_by(email=email).first()
        if tracker:
            tracker.second_last_read_at = second_last
            tracker.last_read_at = timestamp
            logger.info("Updated existing record.")
        else:
            tracker = EmailReadTracker(email=email, last_read_at=timestamp)
            session.add(tracker)
            logger.info("Created new record.")
        session.commit()
        logger.info("Database commit successful.")
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating last read timestamp for email {email}: {e}")


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


def add_processing_summary(
    session, email, total_emails, total_threads, failed_emails, failed_threads
):
    """Add a processing summary record to the EmailProcessingSummary table."""
    try:
        logger.info(f"Adding processing summary for email: {email}")
        summary_record = EmailProcessingSummary(
            email=email,
            total_emails_processed=total_emails,
            total_threads_processed=total_threads,
            failed_emails=failed_emails,
            failed_threads=failed_threads,
            run_timestamp=datetime.now(),
        )
        session.add(summary_record)
        session.commit()
        logger.info(
            "Processing summary added successfully. Database commit successful."
        )
    except Exception as e:
        session.rollback()
        logger.error(f"Error adding processing summary for email {email}: {e}")


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
