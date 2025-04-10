import logging
import os
import traceback
from functools import wraps

from dotenv import load_dotenv
from google.cloud import storage
from sqlalchemy import text
from tasks.email_embedding_tasks import get_chroma_client, sanitize_collection_name
from utils.db_utils import get_db_session
from utils.gcp_logging_utils import setup_gcp_logging

# Initialize logger
logger = setup_gcp_logging("data_delete_task")
logger.info("Initialized logger for data_delete_task")

load_dotenv(os.path.join(os.path.dirname(__file__), "/app/.env"))
# Instantiate a client
storage_client = storage.Client()

# Get the bucket
bucket_name = os.getenv("BUCKET_NAME")
bucket = storage_client.bucket(bucket_name)


def delete_blob(bucket_name, blob_name):
    """Deletes a blob from the bucket."""
    storage_client = storage.Client()

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    generation_match_precondition = None

    blob.reload()  # Fetch blob metadata to use in generation_match_precondition.
    generation_match_precondition = blob.generation

    blob.delete(if_generation_match=generation_match_precondition)

    logger.info(f"Blob {blob_name} deleted.")


def delete_from_gcp(**context):
    try:
        dag_run = context["dag_run"]
        conf = dag_run.conf
        email_id = conf.get("email_address")
        user_id = conf.get("user_id")
        storage_client = storage.Client()
        # Get the bucket
        bucket = storage_client.bucket(bucket_name)
        to_delete = []
        logger.info("files to be deleted: ")
        for blob in bucket.list_blobs():
            if str(blob.name).__contains__(f"{user_id}/{email_id}"):
                to_delete.append(blob.name)
                logger.info(blob.name)
        logger.info("starting to delete files")
        for file_name in to_delete:
            delete_blob(bucket_name, file_name)
    except Exception as e:
        logger.error(f"Error in deletion of files: {e}")
        raise


def delete_embeddings(**context):
    """
    Delete embeddings from ChromaDB for a specific user's email.
    Filters documents where the 'to' field in metadata matches the email address.
    """
    try:
        dag_run = context["dag_run"]
        conf = dag_run.conf
        email_id = conf.get("email_address")
        user_id = conf.get("user_id")

        logger.info(
            f"Attempting to delete embeddings for user {user_id} and email {email_id}"
        )

        chroma_client = get_chroma_client()
        collection_name = sanitize_collection_name(user_id)

        # Check if collection exists
        collections = chroma_client.list_collections()
        if collection_name not in [col.name for col in collections]:
            logger.warning(f"Collection {collection_name} not found for user {user_id}")
            return

        # Get the collection
        collection = chroma_client.get_collection(name=collection_name)

        # Query documents where 'to' field matches the email_id
        results = collection.get(where={"to": email_id})

        if results and results["ids"]:
            document_count = len(results["ids"])
            # Delete the matching documents
            collection.delete(ids=results["ids"])
            logger.info(
                f"Successfully deleted {document_count} embeddings for email {email_id} from collection {collection_name}"
            )
        else:
            logger.info(
                f"No embeddings found for email {email_id} in collection {collection_name}"
            )

    except Exception as e:
        logger.error(f"Error deleting embeddings: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise Exception(f"Failed to delete embeddings: {str(e)}")


def delete_from_postgres(**context):
    """Delete all data related to a user's email from PostgreSQL tables."""
    try:
        dag_run = context["dag_run"]
        conf = dag_run.conf
        email_id = conf.get("email_address")
        user_id = conf.get("user_id")

        session = get_db_session()

        # Define DELETE queries for all relevant tables
        queries = [
            """DELETE FROM google_tokens 
               WHERE user_id = :user_id AND email = :email""",
            """DELETE FROM email_read_tracker 
               WHERE user_id = :user_id AND email = :email""",
            """DELETE FROM email_processing_summary 
               WHERE user_id = :user_id AND email = :email""",
            """DELETE FROM email_preprocessing_summary 
               WHERE user_id = :user_id AND email = :email""",
            """DELETE FROM email_run_status 
               WHERE user_id = :user_id AND email = :email""",
        ]

        try:
            # Execute each DELETE query
            for query in queries:
                result = session.execute(
                    text(query), {"user_id": user_id, "email": email_id}
                )
                logger.info(
                    f"Deleted {result.rowcount} rows from {query.split('FROM')[1].split('WHERE')[0].strip()}"
                )

            # Commit all changes
            session.commit()
            logger.info(
                f"Successfully deleted all data for user {user_id} and email {email_id}"
            )

        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting data: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    except Exception as e:
        logger.error(f"Error in delete_from_postgres: {str(e)}")
        raise

    finally:
        session.close()
