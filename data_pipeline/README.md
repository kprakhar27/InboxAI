# Inbox AI Data Pipeline Overview

This document provides an overview of the data pipeline and the steps to set up the necessary environment using Docker and environment variables.

## Overview

The data pipeline fetches emails for a user and processes them in the following steps:

1. **Batching Emails**: The pipeline divides the fetched emails into batches of 50 emails each.
2. **Fetching Emails**: It retrieves the emails from Gmail using the Gmail API.
3. **Storing Emails**: The fetched emails are then written to Google Cloud Storage (GCS).
4. **Preprocessing**: The emails stored in GCS are preprocessed to clean and prepare the data.
5. **Creating Embeddings**: The preprocessed emails are converted into embeddings.
6. **Storing Embeddings**: The embeddings are stored in a Vector Database for efficient retrieval and analysis.

Refer to the `vector_db` folder for more details on how the embeddings are managed and stored.

## Setup Steps

### Docker Setup

1. **Clone the Repository**: Clone the project repository from GitHub:

   ```sh
   git clone https://github.com/kprakhar27/InboxAI.git
   cd data_pipeline
   ```

2. **Install Docker**: Ensure Docker is installed on your machine. You can download it from [Docker's official website](https://www.docker.com/get-started).

3. **Run Docker Compose**: Build and start the Docker containers using Docker Compose:

   ```sh
   docker compose up --build -d
   ```

4. **Run Vector DB Docker**: Start the Vector Database Docker container to ensure it is up and running:
   ```sh
   docker compose -f vector_db/docker-compose.yml up --build -d
   ```

### Environment Variables Setup

1. **Create `.env` File**: In the project root directory, create a `.env` file to store environment variables.

2. **Define Variables**: Add the necessary environment variables to the `.env` file. For example:
   The environment file contains numerous values that may require refactoring due to the current setup of our backend and PostgreSQL. If you need API keys or service account tokens, please contact Pradnyesh at <choudhari.pra@northeastern.edu> to obtain the necessary credentials.

   ```sh
   DB_NAME=<your_db_name>
   DB_USER=<your_db_user>
   DB_PASSWORD=<your_db_password>
   DB_HOST=<your_db_host>
   DB_PORT=<your_db_port>
   SECRET_KEY=<your_secret_key>
   JWT_SECRET_KEY=<your_jwt_secret_key>
   REDIRECT_URI=<your_redirect_uri>
   BUCKET_NAME=<your_bucket_name>
   CREDENTIAL_PATH_FOR_GMAIL_API=<your_credential_path_for_gmail_api>
   GOOGLE_APPLICATION_CREDENTIALS=<your_google_application_credentials>
   _AIRFLOW_WWW_USER_USERNAME=<your_airflow_www_user_username>
   _AIRFLOW_WWW_USER_PASSWORD=<your_airflow_www_user_password>
   AIRFLOW_PROJ_DIR=<your_airflow_proj_dir>
   AIRFLOW_UID=<your_airflow_uid>
   AIRFLOW_GID=<your_airflow_gid>
   AIRFLOW_DAGS_DIR=<your_airflow_dags_dir>
   AIRFLOW_PLUGINS_DIR=<your_airflow_plugins_dir>
   AIRFLOW_LOGS_DIR=<your_airflow_logs_dir>
   AIRFLOW_DB_NAME=<your_airflow_db_name>
   AIRFLOW_DB_USER=<your_airflow_db_user>
   AIRFLOW_DB_PASSWORD=<your_airflow_db_password>
   AIRFLOW__CELERY__RESULT_BACKEND=<your_airflow_celery_result_backend>
   AIRFLOW__CELERY__BROKER_URL=<your_airflow_celery_broker_url>
   AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=<your_airflow_database_sql_alchemy_conn>
   AIRFLOW__SMTP__SMTP_HOST=<your_airflow_smtp_host>
   AIRFLOW__SMTP__SMTP_PORT=<your_airflow_smtp_port>
   AIRFLOW__SMTP__SMTP_USER=<your_airflow_smtp_user>
   AIRFLOW__SMTP__SMTP_PASSWORD=<your_airflow_smtp_password>
   AIRFLOW__SMTP__SMTP_MAIL_FROM=<your_airflow_smtp_mail_from>
   AIRFLOW__SMTP__SMTP_STARTTLS=<your_airflow_smtp_starttls>
   AIRFLOW__SMTP__SMTP_SSL=<your_airflow_smtp_ssl>
   AIRFLOW_ALERT_EMAIL=<your_airflow_alert_email>
   SMTP_HOST=<your_smtp_host>
   SMTP_PORT=<your_smtp_port>
   SMTP_USER=<your_smtp_user>
   SMTP_PASSWORD=<your_smtp_password>
   SMTP_MAIL_FROM=<your_smtp_mail_from>
   SMTP_STARTTLS=<your_smtp_starttls>
   SMTP_SSL=<your_smtp_ssl>
   ALERT_EMAIL=<your_alert_email>
   OPENAI_API_KEY=<your_openai_api_key>
   CHROMA_HOST_URL=<your_chroma_host_url>
   ```

### Google Service Account and Gmail API Configuration

The configuration files for the Google Service Account and Gmail API should be placed inside the `data_pipeline/airflow/config` directory.

1. **Google Service Account Configuration**: To configure the Google Service Account, follow the instructions provided in the [Google Cloud documentation](https://cloud.google.com/iam/docs/creating-managing-service-accounts).

2. **Gmail API Configuration**: To set up the Gmail API, refer to the [Gmail API documentation](https://developers.google.com/gmail/api/quickstart/python).

By following these steps, you will have a fully functional data pipeline environment set up using Docker and environment variables.

### Accessing the Airflow UI

To access the Airflow UI, follow these steps:

**Open Airflow UI**: Open your web browser and navigate to `http://localhost:8080`. You should see the Airflow login page.

Once logged in, you will have access to the Airflow UI where you can monitor and manage your data pipeline workflows.
