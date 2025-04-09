import logging
import os
import re
from typing import Optional

import chromadb
import numpy as np
import openai
import pandas as pd
from chromadb.config import Settings
from dotenv import load_dotenv
from google.cloud import storage
from utils.gcp_logging_utils import setup_gcp_logging

# Initialize logger
logger = setup_gcp_logging("email_embedding_tasks")
logger.info("Initialized logger for email_embedding_tasks")
LOCAL_TMP_DIR = "/tmp/email_embeddings"

# Move this to the top of the file, before any OpenAI operations
load_dotenv(os.path.join(os.path.dirname(__file__), "/app/.env"))


def get_openai_client():
    """
    Initialize OpenAI client with API key from environment variable.

    returns:
        openai.Client: OpenAI client instance.
    raises:
        ValueError: If OPENAI_API_KEY environment variable is not set.
    """
    api = os.getenv("OPENAI_API_KEY")
    if not api:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    return openai.Client(api_key=api)


def sanitize_collection_name(email: str) -> str:
    # Replace @ and . with underscore
    sanitized = email.replace("@", "_").replace(".", "_")
    # Remove any consecutive underscores
    while "__" in sanitized:
        sanitized = sanitized.replace("__", "_")
    # Ensure it starts and ends with alphanumeric
    sanitized = sanitized.strip("_")
    # Add prefix if too short
    if len(sanitized) < 3:
        sanitized = f"user_{sanitized}"
    # Truncate if too long
    if len(sanitized) > 63:
        sanitized = sanitized[:63].rstrip("_")
    return sanitized


def get_chroma_client():
    try:
        chroma_client = chromadb.HttpClient(
            host=os.getenv("CHROMA_HOST_URL"), port=os.getenv("CHROMA_PORT")
        )
        logger.info("Successfully connected to Chroma client.")
        return chroma_client
    except Exception as e:
        logger.error(f"Error connecting to Chroma client: {e}")
        raise


# Ensure the temporary directory exists
os.makedirs(LOCAL_TMP_DIR, exist_ok=True)


def upload_to_chroma(user_id, embedded_data_path, client) -> None:
    """
    Upload data to Chroma
    """
    try:
        # Load the data
        df = pd.read_parquet(embedded_data_path)

        # Sanitize the user ID
        collection_name = sanitize_collection_name(user_id)
        logger.info(f"Using collection name: {collection_name} for user: {user_id}")
        collection = client.get_or_create_collection(name=collection_name)

        # Upload data to Chroma
        collection.upsert(
            documents=df.redacted_text.tolist(),
            embeddings=df.embeddings.tolist(),
            metadatas=df.metadata.tolist(),
            ids=df.message_id.tolist(),
        )
        logger.info(f"Successfully uploaded data to Chroma for user {user_id}.")
    except Exception as e:
        logger.error(f"Error uploading data to Chroma: {e}")
        raise


def download_processed_from_gcs(**context):
    try:
        dag_run = context["dag_run"]
        conf = dag_run.conf
        gcs_uri = conf.get("processed_gcs_uri")
        logger.info(f"Downloading processed data from GCS URI: {gcs_uri}")

        # Parse bucket name and object path from GCS URI
        parts = gcs_uri.replace("gs://", "").split("/", 1)
        bucket_name = parts[0]
        object_name = parts[1]

        local_path = f"{LOCAL_TMP_DIR}/processed_emails_{context['ds']}.parquet"

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
    except Exception as e:
        logger.error(f"Error downloading processed data from GCS: {e}")
        raise


def extract_email(email):
    match = re.search(r"[\w\.-]+@[\w\.-]+", email)
    return match.group(0) if match else None


def chunk_text(text: str, max_tokens: int = 8000) -> list[str]:
    """Split text into chunks that fit within token limit."""
    # Rough estimate: 1 token ≈ 4 characters
    max_chars = max_tokens * 4
    chunks = []

    while len(text) > max_chars:
        # Find last period before max_chars
        split_point = text[:max_chars].rfind(".")
        if split_point == -1:
            split_point = max_chars

        chunks.append(text[: split_point + 1])
        text = text[split_point + 1 :]

    chunks.append(text)
    return chunks


def generate_embeddings(**context):
    try:
        client = get_openai_client()
        local_file_path = context["ti"].xcom_pull(key="local_file_path")
        execution_date = context["ds"]
        embedded_data_path = (
            f"{LOCAL_TMP_DIR}/processed_emails_{execution_date}.parquet"
        )

        df = pd.read_parquet(local_file_path)
        df["labels"] = df["labels"].astype(str)

        # Create metadata column
        df["metadata"] = df.apply(
            lambda row: {
                "from": extract_email(row.from_email),
                "date": row.date,
                "labels": row.labels,
                "to": extract_email(row.to[0]),
            },
            axis=1,
        )

        # Generate embeddings with chunking
        def get_embedding(text):
            chunks = chunk_text(text)
            if len(chunks) == 1:
                # Single chunk - return embedding directly
                return (
                    client.embeddings.create(input=text, model="text-embedding-3-small")
                    .data[0]
                    .embedding
                )
            else:
                # Multiple chunks - average their embeddings
                chunk_embeddings = [
                    client.embeddings.create(
                        input=chunk, model="text-embedding-3-small"
                    )
                    .data[0]
                    .embedding
                    for chunk in chunks
                ]
                return np.mean(chunk_embeddings, axis=0).tolist()

        # Apply embedding generation with progress logging
        total_rows = len(df)
        df["embeddings"] = df.apply(
            lambda row: get_embedding(row.redacted_text),
            axis=1,
        )

        # Save results
        os.makedirs(os.path.dirname(embedded_data_path), exist_ok=True)
        df.to_parquet(embedded_data_path)
        logger.info(f"Successfully saved embeddings to {embedded_data_path}")

        context["ti"].xcom_push(key="embedded_data_path", value=embedded_data_path)
        return True

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise


def upsert_embeddings(**context) -> bool:
    try:
        dag_run = context["dag_run"]
        conf = dag_run.conf
        gcs_uri = conf.get("processed_gcs_uri")
        embedded_data_path = context["ti"].xcom_pull(key="embedded_data_path")
        user_id = conf.get("user_id")
        client = get_chroma_client()

        # Parse User ID from GCS URI if not provided in config
        if not user_id:
            parts = gcs_uri.replace("gs://", "").split("/")
            # Using index 4 to get 'user123' from gs://bucket_name/processed/data/user123/file.parquet
            user_id = parts[2] if len(parts) > 4 else "default_user"

        logger.info(f"Upserting embeddings for user {user_id}")

        upload_to_chroma(user_id, embedded_data_path, client)

        return True
    except Exception as e:
        logger.error(f"Error upserting embeddings: {e}")
        raise
