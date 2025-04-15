import hashlib
import uuid

from flask_sqlalchemy import SQLAlchemy
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
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
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
    user_id = db.Column(UUID(as_uuid=True), nullable=False)
    email = db.Column(db.String(120), nullable=False)
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
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    total_emails_processed = db.Column(db.Integer, nullable=False)
    total_threads_processed = db.Column(db.Integer, nullable=False)
    failed_emails = db.Column(db.Integer, nullable=False)
    failed_threads = db.Column(db.Integer, nullable=False)
    run_timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())


class EmailPreprocessingSummary(db.Model):
    __tablename__ = "email_preprocessing_summary"

    run_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    total_emails_processed = db.Column(db.Integer, nullable=False)
    total_threads_processed = db.Column(db.Integer, nullable=False)
    successful_emails = db.Column(db.Integer, nullable=False)
    successful_threads = db.Column(db.Integer, nullable=False)
    failed_emails = db.Column(db.Integer, nullable=False)
    failed_threads = db.Column(db.Integer, nullable=False)
    run_timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())


run_status_enum = ENUM(
    "STARTED", "COMPLETED", "FAILED", name="run_status_enum", create_type=True
)


class EmailRunStatus(db.Model):
    __tablename__ = "email_run_status"

    user_id = db.Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    email = db.Column(db.String(120), primary_key=True, nullable=False)
    run_status = db.Column(run_status_enum, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

class Chat(db.Model):
    __tablename__ = "chats"
    
    chat_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(255), default='New Chat')
    created_at = db.Column(db.DateTime(timezone=True), default=db.func.current_timestamp())
    
    # Relationships
    messages = db.relationship('Message', backref='chat', lazy=True)
    user = db.relationship('Users', backref='chats', lazy=True)


class RAG(db.Model):
    __tablename__ = "rag"
    
    rag_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rag_name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=db.func.current_timestamp())
    
    # Relationships
    messages = db.relationship('Message', backref='rag_source', lazy=True)


class Message(db.Model):
    __tablename__ = "messages"
    
    message_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id = db.Column(UUID(as_uuid=True), db.ForeignKey("chats.chat_id"), nullable=False)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    query_hash = db.Column(db.String(32), nullable=False)
    response_hash = db.Column(db.String(32), nullable=False)
    rag_id = db.Column(UUID(as_uuid=True), db.ForeignKey("rag.rag_id"), nullable=False)
    response_time_ms = db.Column(db.Integer)
    feedback = db.Column(db.Boolean)
    created_at = db.Column(db.DateTime(timezone=True), default=db.func.current_timestamp())
    
    # Relationships
    user = db.relationship('Users', backref='messages', lazy=True)
    
    @staticmethod
    def hash_text(text: str) -> str:
        """Create MD5 hash of input text"""
        return hashlib.md5(text.encode()).hexdigest()
    
    def set_query(self, query: str):
        """Set query hash from original text"""
        self.query_hash = self.hash_text(query)
    
    def set_response(self, response: str):
        """Set response hash from original text"""
        self.response_hash = self.hash_text(response)
