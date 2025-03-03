import logging
import os
import traceback
from typing import Optional

import chromadb
import numpy as np
import openai
import pandas as pd
from chromadb.config import Settings
from google.cloud import storage

# Initialize logging
logger = logging.getLogger(__name__)
LOCAL_TMP_DIR = "/tmp/email_embeddings"

openai.api_key = ""


def get_chroma_client():
    chroma_client = chromadb.HttpClient(host="", port=8000)
    return chroma_client


# Ensure the temporary directory exists
os.makedirs(LOCAL_TMP_DIR, exist_ok=True)


def upload_to_chroma(user_id, embedded_data_path, client) -> None:
    """
    Upload data to Chroma
    """
    try:
        # Load the data
        df = pd.read_parquet(embedded_data_path)
        collection = client.get_or_create_collection(name=user_id)

        # Upload data to Chroma
        collection.upsert(
            documents=df.subject.tolist(),
            embeddings=df.embeddings.tolist(),
            metadatas=df.metadata.tolist(),
            ids=df.message_id.tolist(),
        )
    except Exception as e:
        print(f"Error uploading data to Chroma: {e}")


def download_processed_from_gcs(**context):
    dag_run = context["dag_run"]
    conf = dag_run.conf
    gcs_uri = conf.get("processed_gcs_uri")

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


def generate_embeddings(**context):
    local_file_path = context["ti"].xcom_pull(key="local_file_path")
    execution_date = context["ds"]
    embedded_data_path = f"{local_file_path}/embedded_emails_{execution_date}.parquet"
    df = pd.read_parquet(local_file_path)
    df["labels"] = df["labels"].astype(str)
    # using apply function to create a new column
    df["metadata"] = df.apply(
        lambda row: {"from": row.from_email, "date": row.date, "labels": row.labels},
        axis=1,
    )
    df["embeddings"] = df.apply(
        lambda row: openai.embeddings.create(
            input=row.redacted_text, model="text-embedding-3-small"
        ),
        axis=1,
    )

    # Ensure directory exists
    os.makedirs(os.path.dirname(embedded_data_path), exist_ok=True)

    # Save the embedded data to parquet file
    df.to_parquet(embedded_data_path)
    logger.info(f"Successfully saved embeddings to {embedded_data_path}")

    # Push the file path to XCom for the next task
    context["ti"].xcom_push(key="embedded_data_path", value=embedded_data_path)
    return True


def upsert_embeddings(**context) -> bool:
    dag_run = context["dag_run"]
    conf = dag_run.conf
    gcs_uri = conf.get("processed_gcs_uri")
    embedded_data_path = context["ti"].xcom_pull(key="embedded_data_path")
    user_id = conf.get("user_id")
    client = get_chroma_client()

    upload_to_chroma(user_id, embedded_data_path, client)

    return True
