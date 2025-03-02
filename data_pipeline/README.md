# InboxAI Data Pipeline

## Overview

The InboxAI Data Pipeline is a comprehensive ETL (Extract, Transform, Load) system built with Apache Airflow to process email data from Gmail. The pipeline handles authentication, email retrieval, preprocessing, and storage for downstream AI applications.

## Key Components

### DAGs (Directed Acyclic Graphs)

1. **Email Fetch Pipeline (`email_fetch_pipeline.py`)**

   - Authenticates with Gmail API
   - Lists available emails
   - Creates batches for processing

2. **Email Get Pipeline (`email_get_pipeline.py`)**

   - Retrieves full email content
   - Processes emails in batches
   - Saves raw email data

3. **Email Preprocessing Pipeline (`email_preprocessing_pipeline.py`)**
   - Extracts text from HTML content
   - Combines plain text and HTML content
   - Redacts personally identifiable information (PII)
   - Prepares data for embedding generation

### Key Utilities

1. **Gmail Authentication (`gmail_auth.py`)**

   - Handles OAuth2 authentication
   - Manages credentials and token refresh

2. **Email Processing (`preprocessing_utils.py`)**

   - Decodes Base64 URL-encoded content
   - Extracts plain text from HTML
   - Removes PII through regex patterns

3. **Storage Service (`storage_service.py`)**
   - Manages data persistence
   - Handles file operations

## Installation

### Prerequisites

- Python 3.9+
- Docker and Docker Compose
- Gmail API credentials

### Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/InboxAI.git
   cd InboxAI/data_pipeline
   ```

2. Create a .env file with following details

3. Build and run with Docker Compose:
   docker-compose build
   docker-compose up -d

4. Access the Airflow UI at http://localhost:8080

## Usage

### Gmail Authentication

1. Set up a project in the Google Cloud Console
2. Enable the Gmail API
3. Create OAuth2 credentials
4. Add the credentials to the authentication system

### Running the Pipeline

1. Trigger the `email_fetch_pipeline` DAG with parameters:

   - `email_address`: The email address to process
   - `user_id`: User identifier in the system

2. Monitor the pipeline execution in the Airflow UI

3. Access processed data in the database or storage system

## Pipeline Details

### Email Fetch Process

1. Authenticate with Gmail API
2. List available emails
3. Group emails into batches
4. Trigger the processing pipeline for each batch

### Email Processing

1. Retrieve full email content for each batch
2. Decode Base64 URL-encoded content
3. Extract metadata (sender, recipient, date, etc.)
4. Save raw email data

### Preprocessing

1. Extract plain text from HTML content
2. Combine multiple text parts
3. Redact PII (emails, phone numbers, etc.)
4. Clean and normalize text
5. Save processed data for embedding generation

## Troubleshooting

### Common Issues

1. **Authentication Errors**

   - Check OAuth2 token validity
   - Ensure proper scopes are configured

2. **Rate Limiting**

   - The pipeline includes retry mechanisms for API rate limits

3. **Encoding Issues**
   - The system handles various content encoding formats

### Logs

Logs are available in the Airflow UI or in the `logs/` directory within the container.
