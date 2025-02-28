import base64
import json
import logging
import os
from datetime import datetime
from os.path import dirname, join
from typing import List, Optional

from dotenv import load_dotenv
from google.cloud import storage
from models_pydantic import EmailSchema
from pydantic import ValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

dotenv_path = join(dirname(__file__), ".env")
load_dotenv(dotenv_path)


class StorageService:
    def __init__(self):
        self.client = storage.Client()
        self.bucket = self.client.bucket(os.environ.get("BUCKET_NAME"))

    def list_files(self, path):
        """List all files in a given GCS path."""
        try:
            blobs = self.bucket.list_blobs(prefix=path)
            logging.info(f"Listing files in path {path}")
            file_names = [blob.name for blob in blobs]
            return file_names
        except Exception as e:
            logging.error(f"Error listing files in path {path}: {e}")
            return []

    def get_raw_email(self, raw_email_path):
        """Fetch raw email from GCS."""
        try:
            blob = self.bucket.blob(raw_email_path)
            return blob.download_as_string()
        except Exception as e:
            logging.error(f"Error fetching raw email {raw_email_path}: {e}")
            return None

    def save_processed_email(self, processed_email_path, processed_data):
        """Save processed email to GCS."""
        try:
            blob = self.bucket.blob(processed_email_path)
            blob.upload_from_string(json.dumps(processed_data))
            logging.info(f"Saved processed email to {processed_email_path}")
            return True
        except Exception as e:
            logging.error(f"Error saving processed email {processed_email_path}: {e}")
            return False

    def get_raw_thread(self, raw_thread_path):
        """Fetch raw thread from GCS."""
        try:
            blob = self.bucket.blob(raw_thread_path)
            return blob.download_as_string()
        except Exception as e:
            logging.error(f"Error fetching raw thread {raw_thread_path}: {e}")
            return None

    def save_processed_thread(self, processed_thread_path, processed_data):
        """Save processed thread to GCS."""
        try:
            blob = self.bucket.blob(processed_thread_path)
            blob.upload_from_string(json.dumps(processed_data))
            logging.info(f"Saved processed thread to {processed_thread_path}")
            return True
        except Exception as e:
            logging.error(f"Error saving processed thread {processed_thread_path}: {e}")
            return False

    def get_emails_dir(self, email_account, run_id):
        """Get the directory path for storing email files."""
        base_dir = "/tmp/airflow/runs"
        email_dir = f"{base_dir}/{email_account}/preprocessed/{run_id}"

        os.makedirs(email_dir, exist_ok=True)
        logging.info(f"Created directory: {email_dir}")

        return email_dir

    def save_emails_locally(self, email_account, run_id, emails_data):
        """Save emails data locally as JSON."""
        try:
            raw_dir = f"/tmp/airflow/runs/{email_account}/raw/{run_id}"
            os.makedirs(raw_dir, exist_ok=True)
            logging.info(f"Creating directory {raw_dir} if it doesn't exist")

            file_path = f"{raw_dir}/emails.json"
            with open(file_path, "w") as f:
                json.dump(emails_data, f, default=self._json_serializer)

            logging.info(f"Saving emails to {file_path}")
            return file_path
        except Exception as e:
            logging.error(f"Error saving emails locally: {e}")
            return None

    def _json_serializer(self, obj):
        """Helper function for JSON serialization."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    def upload_directory_to_gcs(self, local_dir, bucket_name, gcs_prefix):
        logging.info(
            f"Uploading directory {local_dir} to gs://{bucket_name}/{gcs_prefix}"
        )

        stats = {"total_files": 0, "successful": 0, "failed": 0}

        try:
            # Use the class-level client and bucket instead of creating new ones
            bucket = self.client.bucket(bucket_name)

            if not os.path.exists(local_dir):
                logging.error(f"Local directory does not exist: {local_dir}")
                return stats

            # Walk through the directory
            for root, _, files in os.walk(local_dir):
                for filename in files:
                    stats["total_files"] += 1
                    try:
                        local_path = os.path.join(root, filename)

                        # Calculate the relative path to preserve directory structure
                        relative_path = os.path.relpath(local_path, start=local_dir)
                        gcs_path = f"{gcs_prefix}/{relative_path}".replace("\\", "/")

                        # Create a blob and upload the file
                        blob = bucket.blob(gcs_path)

                        # Read file content directly
                        with open(local_path, "rb") as file:
                            file_content = file.read()

                        # Upload content
                        content_type = self._get_content_type(filename)
                        blob.upload_from_string(file_content, content_type=content_type)

                        logging.info(
                            f"Uploaded {local_path} to gs://{bucket_name}/{gcs_path}"
                        )
                        stats["successful"] += 1

                    except Exception as file_error:
                        logging.error(
                            f"Error uploading file {local_path}: {file_error}"
                        )
                        stats["failed"] += 1
                        continue

            logging.info(
                f"Upload summary: {stats['successful']} successful, {stats['failed']} failed"
            )
            return stats

        except Exception as e:
            logging.error(f"Error uploading directory to GCS: {e}")
            # Return current stats even if the process failed
            return stats

    def _get_content_type(self, filename):
        """Determine content type based on file extension"""
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".json":
            return "application/json"
        elif ext == ".parquet":
            return "application/octet-stream"
        elif ext == ".csv":
            return "text/csv"
        elif ext == ".txt":
            return "text/plain"
        elif ext in [".jpg", ".jpeg"]:
            return "image/jpeg"
        elif ext == ".png":
            return "image/png"
        else:
            return "application/octet-stream"
