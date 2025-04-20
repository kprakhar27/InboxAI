-- ENUM types
CREATE TYPE email_status AS ENUM ('unprocessed', 'processing', 'success', 'failed');
CREATE TYPE run_status_enum AS ENUM ('STARTED', 'COMPLETED', 'FAILED');

-- Table: users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(80) UNIQUE NOT NULL,
    password_hash VARCHAR(120) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_token VARCHAR(500),
    role VARCHAR(50)
);

-- Table: revoked_tokens
CREATE TABLE revoked_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    jti VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: google_tokens
CREATE TABLE google_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    email VARCHAR(120) NOT NULL,
    access_token VARCHAR(500) NOT NULL,
    refresh_token VARCHAR(500) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: email_read_tracker
CREATE TABLE email_read_tracker (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    email VARCHAR(120) NOT NULL,
    second_last_read_at TIMESTAMP,
    last_read_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: email_ready_for_processing
CREATE TABLE email_ready_for_processing (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_to_gcs_timestamp TIMESTAMP NOT NULL,
    email VARCHAR(120) NOT NULL,
    item_type VARCHAR(120) NOT NULL,
    status email_status DEFAULT 'unprocessed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: email_processing_summary
CREATE TABLE email_processing_summary (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    email VARCHAR(120) NOT NULL,
    total_emails_processed INTEGER NOT NULL,
    total_threads_processed INTEGER NOT NULL,
    failed_emails INTEGER NOT NULL,
    failed_threads INTEGER NOT NULL,
    run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: email_embedding_summary
CREATE TABLE email_embedding_summary (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    email VARCHAR(120) NOT NULL,
    total_emails_embedded INTEGER NOT NULL,
    total_threads_embedded INTEGER NOT NULL,
    failed_emails INTEGER NOT NULL,
    failed_threads INTEGER NOT NULL,
    run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: email_preprocessing_summary
CREATE TABLE email_preprocessing_summary (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    email VARCHAR(120) NOT NULL,
    total_emails_processed INTEGER NOT NULL,
    total_threads_processed INTEGER NOT NULL,
    successful_emails INTEGER NOT NULL,
    successful_threads INTEGER NOT NULL,
    failed_emails INTEGER NOT NULL,
    failed_threads INTEGER NOT NULL,
    run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: email_run_status
CREATE TABLE email_run_status (
    user_id UUID NOT NULL,
    email VARCHAR(120) NOT NULL,
    run_status run_status_enum NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, email)
);

-- Table: chats
CREATE TABLE chats (
    chat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    name VARCHAR(255) DEFAULT 'New Chat',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Table: rag
CREATE TABLE rag (
    rag_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rag_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Table: messages
CREATE TABLE messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id UUID NOT NULL REFERENCES chats(chat_id),
    user_id UUID NOT NULL REFERENCES users(id),
    query TEXT NOT NULL,
    response TEXT NOT NULL,
    rag_id UUID NOT NULL REFERENCES rag(rag_id),
    response_time_ms INTEGER,
    feedback BOOLEAN,
    context TEXT NOT NULL,
    is_toxic BOOLEAN DEFAULT FALSE,
    toxicity_response JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
