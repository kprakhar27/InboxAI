import uuid

from sqlalchemy.dialects.postgresql import ENUM, UUID

from . import db

# Define the ENUM type
email_status_enum = ENUM(
    "unprocessed",
    "processing",
    "success",
    "failed",
    name="email_status",
    create_type=False,
)

# define the database tables to use in the backend apis


class Users(db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.TIMESTAMP, default=db.func.current_timestamp())
    access_token = db.Column(db.String(500), nullable=True)
    role = db.Column(db.String(50), nullable=True)


class RevokedToken(db.Model):
    __tablename__ = "revoked_tokens"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jti = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class GoogleToken(db.Model):
    __tablename__ = "google_tokens"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    access_token = db.Column(db.String(500), nullable=False)
    refresh_token = db.Column(db.String(500), nullable=False)
    expires_at = db.Column(db.TIMESTAMP, nullable=False)
    created_at = db.Column(db.TIMESTAMP, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.TIMESTAMP,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )


class EmailReadTracker(db.Model):
    __tablename__ = "email_read_tracker"
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String(120), unique=True, nullable=False)
    second_last_read_at = db.Column(db.DateTime)
    last_read_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )


class EmailReadyForProcessing(db.Model):
    __tablename__ = "email_ready_for_processing"

    run_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_to_gcs_timestamp = db.Column(db.DateTime, nullable=False)
    email = db.Column(db.String(120), nullable=False)
    item_type = db.Column(db.String(120), nullable=False)
    status = db.Column(email_status_enum, default="unprocessed")
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )


class EmailProcessingSummary(db.Model):
    __tablename__ = "email_processing_summary"

    run_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String(120), nullable=False)
    total_emails_processed = db.Column(db.Integer, nullable=False)
    total_threads_processed = db.Column(db.Integer, nullable=False)
    failed_emails = db.Column(db.Integer, nullable=False)
    failed_threads = db.Column(db.Integer, nullable=False)
    run_timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())


class EmailPreprocessingSummary(db.Model):
    __tablename__ = "email_preprocessing_summary"

    run_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String(120), nullable=False)
    total_emails_processed = db.Column(db.Integer, nullable=False)
    total_threads_processed = db.Column(db.Integer, nullable=False)
    successful_emails = db.Column(db.Integer, nullable=False)
    successful_threads = db.Column(db.Integer, nullable=False)
    failed_emails = db.Column(db.Integer, nullable=False)
    failed_threads = db.Column(db.Integer, nullable=False)
    run_timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
