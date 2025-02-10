# Email Processor

A modular system for processing Gmail emails and threads, storing them in Google Cloud Storage, and preparing them for analysis.

## Overview

This module handles:

1. Gmail authentication and token management
2. Email and thread retrieval
3. Storage in Google Cloud Storage
4. Preprocessing pipeline for email analysis

## Directory Structure

```
email_processor/
├── README.md
├── requirements.txt
├── config/
│   └── settings.py          # Configuration variables and constants
├── utils/
│   └── db_handler.py        # Database operations for token management
├── auth/
│   └── gmail_auth.py        # Gmail OAuth2 authentication
├── services/
│   ├── gmail_service.py     # Gmail API interactions
│   └── storage_service.py   # Google Cloud Storage operations
├── pipelines/
│   ├── email_pipeline.py    # Main email processing pipeline
│   └── preprocessing/       # Preprocessing pipeline components
│       ├── __init__.py
│       ├── cleaner.py       # Text cleaning and normalization
│       └── parser.py        # Email parsing (headers, body, attachments)
├── main.py
└── tests/
    └── __init__.py
```

## Features

### Email Processing

- OAuth2 authentication with Gmail API
- Retrieval of emails and thread data
- Secure token storage in PostgreSQL
- Organized storage in Google Cloud Storage
- Thread-safe database operations

### Preprocessing Pipeline

- Email parsing and structure extraction
- Text cleaning and normalization
- Metadata extraction

### Storage Structure

```
email_bucket/
├── emails/
│   └── user@example.com/
│       └── YYYYMMDDHHMM/
│           └── message_id.eml
├── threads/
│   └── user@example.com/
│       └── YYYYMMDDHHMM/
│           └── thread_id.json
└── processed/
    └── user@example.com/
        └── YYYYMMDDHHMM/
            ├── features/
            │   └── features.parquet
            ├── metadata/
            │   └── metadata.json
            └── vectors/
                └── embeddings.npy
```

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Configure environment variables:

```bash
# Create .env file in .env directory
cp .env.example .env/.env
```

3. Set up Google Cloud credentials:

```bash
# Place your credentials.json file in .env directory
mv credentials.json .env/
```

4. Initialize database:

```sql
CREATE TABLE gmail_tokens (
    email VARCHAR(255) PRIMARY KEY,
    token JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Usage

### Basic Usage

```python
from email_processor.main import run_pipeline

result = run_pipeline(
    email_address="user@example.com",
    start_date="2024/01/01",
    end_date="2024/02/10"
)
```

### Flask Integration

```python
from flask import Flask, request, jsonify
from email_processor.main import run_pipeline

app = Flask(__name__)

@app.route('/process-emails', methods=['POST'])
def process_emails():
    data = request.get_json()
    result = run_pipeline(
        email=data['email'],
        start_date=data['start_date'],
        end_date=data['end_date']
    )
    return jsonify(result)
```

### Airflow Integration

```python
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from email_processor.main import run_pipeline

def process_email_dag(email, **context):
    return run_pipeline(
        email=email,
        start_date=context['ds'],
        end_date=context['next_ds']
    )

dag = DAG('email_processing', ...)
process_task = PythonOperator(...)
```

## Preprocessing Pipeline

## TODO

The preprocessing pipeline handles:

1. **Parsing** (`parser.py`)

   - Extract email headers
   - Separate body content
   - Handle attachments
   - Parse HTML/text content

2. **Cleaning** (`cleaner.py`)

   - Remove HTML tags
   - Normalize text
   - Handle encodings
   - Remove noise

3. **Feature Extraction** (`extractor.py`)

   - Extract metadata
   - Generate embeddings
   - Create feature vectors
   - Calculate metrics

4. **Transformation** (`transformer.py`)
   - Convert to analysis-ready format
   - Generate structured data
   - Prepare for model input

### Using the Preprocessing Pipeline

```python
from email_processor.pipelines.preprocessing import EmailPreprocessor

preprocessor = EmailPreprocessor()
processed_data = preprocessor.process(
    email_path="gs://email_bucket/emails/user@example.com/20240210/msg_id.eml"
)
```
