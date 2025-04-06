import logging
import os
import traceback
from functools import wraps

from dotenv import load_dotenv
from google.cloud import storage
from sqlalchemy import text
from tasks.email_embedding_tasks import get_chroma_client
from utils.db_utils import get_db_session

logger = logging.getLogger(__name__)
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
    try:
        dag_run = context["dag_run"]
        conf = dag_run.conf
        email_id = conf.get("email_address")
        user_id = conf.get("user_id")
        chroma_client = get_chroma_client()
        if user_id in chroma_client.list_collections():
            collection = chroma_client.get_collection(user_id)
        else:
            logger.error("Collection not found")
            raise Exception("Collection not found")
        results = collection.get(where={"to": email_id})
        document_ids = results["ids"]
        if document_ids:
            # Delete documents by IDs
            collection.delete(ids=document_ids)
            logger.info(
                f"Deleted {len(document_ids)} documents for email_id: {email_id}"
            )
        else:
            logger.info(f"No documents found for email_id: {email_id}")
    except Exception as e:
        logger.error(f"error in deleting embeddings : {e}")


def delete_from_postgres(**context):
    try:
        dag_run = context["dag_run"]
        conf = dag_run.conf
        email_id = conf.get("email_address")
        user_id = conf.get("user_id")
        session = get_db_session()
        # Attempt to execute the DELETE query
        query = text(
            """
            DELETE FROM google_tokens WHERE user_id = :id AND email = :email
        """
        )

        # Execute the DELETE query
        result = session.execute(
            query, {"id": user_id, "email": email_id}  # UUID as string
        )

        # Commit the transaction
        session.commit()

        if result.rowcount > 0:
            logger.info(f"Deleted user: {email_id} (ID: {user_id})")
        else:
            logger.info(f"No user found with ID: {user_id} and username: {email_id}")
    except Exception as e:
        # Rollback if there was an error
        session.rollback()
        logger.info(f"Error in deleting from postgres: {e}")

    finally:
        # Close the session
        session.close()
