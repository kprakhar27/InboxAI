import base64
import json
import logging
from datetime import datetime

from google.cloud import storage

from backend.config import BUCKET_NAME, EMAIL_FOLDER, THREAD_FOLDER


class StorageService:
    def __init__(self):
        self.client = storage.Client()
        self.bucket = self.client.bucket(BUCKET_NAME)

    def save_raw_email(self, email_address, msg_id, raw_msg):
        try:
            now = datetime.now().strftime("%Y%m%d%H%M")
            blob_name = f"{EMAIL_FOLDER}/raw/{email_address}/{now}/{msg_id}.eml"
            raw_email = base64.urlsafe_b64decode(raw_msg["raw"].encode("ASCII"))

            blob = self.bucket.blob(blob_name)
            blob.upload_from_string(raw_email)
            logging.info(f"Saved email {msg_id} to gs://{BUCKET_NAME}/{blob_name}")
            return blob_name
        except Exception as e:
            logging.error(f"Error saving email {msg_id}: {e}")
            return None

    def save_raw_thread(self, email_address, thread_id, thread_data):
        try:
            now = datetime.now().strftime("%Y%m%d%H%M")
            blob_name = f"{THREAD_FOLDER}/raw/{email_address}/{now}/{thread_id}.json"

            blob = self.bucket.blob(blob_name)
            blob.upload_from_string(json.dumps(thread_data))
            logging.info(f"Saved thread {thread_id} to gs://{BUCKET_NAME}/{blob_name}")
            return blob_name
        except Exception as e:
            logging.error(f"Error saving thread {thread_id}: {e}")
            return None
