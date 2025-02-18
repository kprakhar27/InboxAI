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
