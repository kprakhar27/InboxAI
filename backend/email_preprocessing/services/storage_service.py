import base64
import json
import logging
import os
from datetime import datetime
from os.path import dirname, join

from dotenv import load_dotenv
from google.cloud import storage

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

    def save_raw_email(self, email_address, msg_id, raw_msg):
        try:
            now = datetime.now().strftime("%m%d%Yat%H%M")
            blob_name = f"{os.environ.get('EMAIL_FOLDER')}/raw/{email_address}/{now}/{msg_id}.eml"
            raw_email = base64.urlsafe_b64decode(raw_msg["raw"].encode("ASCII"))

            blob = self.bucket.blob(blob_name)
            blob.upload_from_string(raw_email)
            logging.info(
                f"Saved email {msg_id} to gs://{os.environ.get('BUCKET_NAME')}/{blob_name}"
            )
            return blob_name
        except Exception as e:
            logging.error(f"Error saving email {msg_id}: {e}")
            return None

    def save_raw_thread(self, email_address, thread_id, thread_data):
        try:
            now = datetime.now().strftime("%m%d%Yat%H%M")
            blob_name = f"{os.environ.get('THREAD_FOLDER')}/raw/{email_address}/{now}/{thread_id}.json"

            blob = self.bucket.blob(blob_name)
            blob.upload_from_string(json.dumps(thread_data))
            logging.info(
                f"Saved thread {thread_id} to gs://{os.environ.get('BUCKET_NAME')}/{blob_name}"
            )
            return blob_name
        except Exception as e:
            logging.error(f"Error saving thread {thread_id}: {e}")
            return None

    def list_files(self, path):
        """List all files in a given GCS path."""
        try:
            blobs = self.bucket.list_blobs(prefix=path)
            return [blob.name for blob in blobs]
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
