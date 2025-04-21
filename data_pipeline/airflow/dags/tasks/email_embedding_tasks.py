import logging
import os
import re
from typing import Optional

import chromadb
import numpy as np
import openai
import pandas as pd
import tiktoken
from chromadb.config import Settings
from dotenv import load_dotenv
from google.cloud import storage
from utils.db_utils import add_embedding_summary, get_db_session
from utils.gcp_logging_utils import setup_gcp_logging

# Initialize logger
logger = setup_gcp_logging("email_embedding_tasks")
logger.info("Initialized logger for email_embedding_tasks")
LOCAL_TMP_DIR = "/tmp/email_embeddings"

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), "/app/.env"))


def get_openai_client():
    api = os.getenv("OPENAI_API_KEY")
    if not api:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    return openai.Client(api_key=api)


def sanitize_collection_name(email: str) -> str:
    sanitized = email.replace("@", "_").replace(".", "_")
    while "__" in sanitized:
        sanitized = sanitized.replace("__", "_")
    sanitized = sanitized.strip("_")
    if len(sanitized) < 3:
        sanitized = f"user_{sanitized}"
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


os.makedirs(LOCAL_TMP_DIR, exist_ok=True)


def upload_to_chroma(user_id, embedded_data_path, client) -> None:
    try:
        df = pd.read_parquet(embedded_data_path)
        items_to_upsert = len(df)
        logger.info(f"Loaded {items_to_upsert} items from parquet file")

        collection_name = sanitize_collection_name(user_id)
        logger.info(f"Using collection name: {collection_name} for user: {user_id}")
        collection = client.get_or_create_collection(
            name=collection_name, metadata=None, embedding_function=None
        )

        count_before = collection.count()
        logger.info(
            f"Collection {collection_name} has {count_before} items before upsert"
        )

        collection.upsert(
            documents=df.redacted_text.tolist(),
            embeddings=df.embeddings.tolist(),
            metadatas=df.metadata.tolist(),
            ids=df.message_id.tolist(),
        )

        count_after = collection.count()
        new_items = count_after - count_before

        if new_items > 0:
            logger.info(f"Added {new_items} new items to collection {collection_name}")
            if new_items != items_to_upsert:
                logger.warning(
                    f"Count mismatch: Expected to add {items_to_upsert} items but added {new_items} items"
                )
        elif new_items == 0 and items_to_upsert > 0:
            logger.info(
                f"Updated {items_to_upsert} existing items in collection {collection_name}"
            )
        else:
            error_msg = f"Invalid count change: {count_before} → {count_after} ({new_items} difference)"
            logger.error(error_msg)
            raise ValueError(error_msg)

        expected_ids = set(df.message_id.tolist())
        actual_ids = set(collection.get()["ids"])
        missing_ids = expected_ids - actual_ids

        if missing_ids:
            error_msg = f"Missing {len(missing_ids)} IDs after upsert"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(
            f"Successfully uploaded data to Chroma for user {user_id}. Collection now has {count_after} total items."
        )

    except Exception as e:
        logger.error(f"Error uploading data to Chroma: {str(e)}")
        raise


def download_processed_from_gcs(**context):
    try:
        dag_run = context["dag_run"]
        conf = dag_run.conf
        gcs_uri = conf.get("processed_gcs_uri")
        logger.info(f"Downloading processed data from GCS URI: {gcs_uri}")

        parts = gcs_uri.replace("gs://", "").split("/", 1)
        bucket_name, object_name = parts[0], parts[1]

        local_path = f"{LOCAL_TMP_DIR}/processed_emails_{context['ds']}.parquet"
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

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

def chunk_text(text: str, max_tokens: int = 8192) -> list[str]:
    tokenizer = tiktoken.encoding_for_model("text-embedding-3-small")
    tokens = tokenizer.encode(text)
    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk_tokens = tokens[i : i + max_tokens]
        chunks.append(tokenizer.decode(chunk_tokens))
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

        df["metadata"] = df.apply(
            lambda row: {
                "from": extract_email(row.from_email),
                "date": row.date,
                "labels": row.labels,
                "to": extract_email(row.to[0]),
            },
            axis=1,
        )

        def get_embedding(text):
            chunks = chunk_text(text)
            if len(chunks) == 1:
                return (
                    client.embeddings.create(
                        input=chunks[0], model="text-embedding-3-small"
                    )
                    .data[0]
                    .embedding
                )
            else:
                chunk_embeddings = [
                    client.embeddings.create(
                        input=chunk, model="text-embedding-3-small"
                    )
                    .data[0]
                    .embedding
                    for chunk in chunks
                ]
                return np.mean(chunk_embeddings, axis=0).tolist()

        df["embeddings"] = df.apply(
            lambda row: get_embedding(row.redacted_text), axis=1
        )

        os.makedirs(os.path.dirname(embedded_data_path), exist_ok=True)
        df.to_parquet(embedded_data_path)
        logger.info(f"Successfully saved embeddings to {embedded_data_path}")

        total_emails = len(df)
        successful_emails = int(df["embeddings"].notnull().sum())
        failed_emails = total_emails - successful_emails

        dag_run = context["dag_run"]
        conf = dag_run.conf
        user_id = conf.get("user_id")
        email = conf.get("email")

        session = get_db_session()
        add_embedding_summary(
            session=session,
            user_id=user_id,
            email=email,
            total_emails_embedded=total_emails,
            total_threads_embedded=0,
            failed_emails=failed_emails,
            failed_threads=0,
        )

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

        if not user_id:
            parts = gcs_uri.replace("gs://", "").split("/")
            user_id = parts[2] if len(parts) > 4 else "default_user"

        logger.info(f"Upserting embeddings for user {user_id}")
        upload_to_chroma(user_id, embedded_data_path, client)

        return True
    except Exception as e:
        logger.error(f"Error upserting embeddings: {e}")
        raise
