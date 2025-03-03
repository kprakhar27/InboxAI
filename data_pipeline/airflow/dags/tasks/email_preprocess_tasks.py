import base64
import logging
import os

import pandas as pd
from airflow.exceptions import AirflowSkipException
from airflow.models import Variable
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from google.cloud import storage
from services.storage_service import StorageService
from utils.airflow_utils import decode_base64_url_safe
from utils.preprocessing_utils import EmailPreprocessor

# Initialize logging
logger = logging.getLogger(__name__)

LOCAL_TMP_DIR = "/tmp/email_preprocessing"

# Ensure the temporary directory exists
os.makedirs(LOCAL_TMP_DIR, exist_ok=True)


def download_raw_from_gcs(**context):
    # Use direct GCS URI for the source file
    dag_run = context["dag_run"]
    conf = dag_run.conf
    gcs_uri = conf.get("gcs_uri")

    # Parse bucket name and object path from GCS URI
    parts = gcs_uri.replace("gs://", "").split("/", 1)
    bucket_name = parts[0]
    object_name = parts[1] + "/emails.parquet"

    local_path = f"{LOCAL_TMP_DIR}/raw_emails_{context['ds']}.parquet"

    logger.info(f"Downloading from GCS URI: {gcs_uri}")
    logger.info(f"Parsed - Bucket: {bucket_name}, Object: {object_name}")

    # Ensure directory exists
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    # Download the file
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    blob.download_to_filename(local_path)

    logger.info(f"Successfully downloaded file to {local_path}")
    context["ti"].xcom_push(key="local_file_path", value=local_path)
    return local_path


def preprocess_emails(**context):
    """
    Preprocess downloaded emails and save processed version.
    """
    logger.info("Starting email preprocessing")

    execution_date = context["ds"]
    raw_data_path = f"{LOCAL_TMP_DIR}/raw_emails_{execution_date}.parquet"
    processed_data_path = f"{LOCAL_TMP_DIR}/processed_emails_{execution_date}.parquet"

    try:
        # Initialize preprocessor
        preprocessor = EmailPreprocessor()

        # Load raw data
        logger.info(f"Loading raw email data from {raw_data_path}")
        emails_df = preprocessor.load_data(raw_data_path)
        logger.info(f"Loaded {len(emails_df)} emails for preprocessing")

        # Apply decoding to Base64 content
        logger.info("Decoding Base64 encoded content")
        if "plain_text" in emails_df.columns:
            emails_df["plain_text_decoded"] = emails_df["plain_text"].apply(
                decode_base64_url_safe
            )
        if "html" in emails_df.columns:
            emails_df["html_decoded"] = emails_df["html"].apply(decode_base64_url_safe)

        # Apply preprocessing steps
        logger.info("Applying preprocessing steps to emails")
        processed_df = preprocessor.preprocess(emails_df)
        logger.info(f"Successfully preprocessed {len(processed_df)} emails")

        # Save processed data
        logger.info(f"Saving processed data to {processed_data_path}")
        processed_df.to_parquet(processed_data_path, index=False)
        logger.info(f"Successfully saved processed data to {processed_data_path}")

        # Push metadata to XCom
        context["ti"].xcom_push(
            key="preprocessing_metadata",
            value={
                "raw_count": len(emails_df),
                "processed_count": len(processed_df),
                "execution_date": execution_date,
            },
        )

        return True

    except Exception as e:
        logger.error(f"Email preprocessing failed: {str(e)}")
        raise


def upload_processed_to_gcs(**context):
    """
    Upload processed emails to Google Cloud Storage.
    """
    logger.info("Starting upload of processed emails to GCS")

    # Get the original GCS URI from dag_run.conf
    dag_run = context["dag_run"]
    conf = dag_run.conf
    gcs_uri = conf.get("gcs_uri")

    # Parse bucket name and create destination path
    parts = gcs_uri.replace("gs://", "").split("/", 1)
    bucket_name = parts[0]
    base_path = parts[1].replace("raw", "processed", 1)

    # Define local and destination paths
    execution_date = context["ds"]
    local_path = f"{LOCAL_TMP_DIR}/processed_emails_{execution_date}.parquet"
    object_name = f"{base_path}/processed_emails.parquet"

    logger.info(f"Uploading from local path: {local_path}")
    logger.info(f"Uploading to GCS - Bucket: {bucket_name}, Object: {object_name}")

    # Upload the file
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    blob.upload_from_filename(local_path)

    logger.info(
        f"Successfully uploaded processed emails to gs://{bucket_name}/{object_name}"
    )

    # Push the GCS URI to XCom
    context["ti"].xcom_push(key="processed_gcs_uri", value=gcs_uri)

    return f"gs://{bucket_name}/{object_name}"


def trigger_embedding_pipeline(**context):
    """
    Trigger the email embedding generation pipeline.
    """
    logger.info("Triggering email embedding generation pipeline")

    try:
        # Get metadata from previous task
        proceesed_gcs_uri = context["ti"].xcom_pull(
            task_ids="upload_processed_to_gcs", key="processed_gcs_uri"
        )

        # Pass execution date to the triggered DAG
        execution_date = context.get("ds")

        logger.info(
            f"Triggering embedding pipeline for execution date: {execution_date}"
        )

        trigger_task = TriggerDagRunOperator(
            task_id="trigger_embedding_dag",
            trigger_dag_id="email_embedding_generation_pipeline",
            conf={
                "execution_date": execution_date,
                "proceesed_gcs_uri": proceesed_gcs_uri,
            },
            reset_dag_run=True,
            wait_for_completion=False,
        )
        trigger_task.execute(context=context)

        logger.info(f"Successfully triggered embedding pipeline.")
        return True

    except Exception as e:
        logger.error(f"Failed to trigger embedding pipeline: {str(e)}")
        raise
