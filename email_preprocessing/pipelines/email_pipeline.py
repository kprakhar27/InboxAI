import json
import logging
import os
import sys
from datetime import datetime
from email import policy
from email.parser import BytesParser

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from email_preprocessing.auth.gmail_auth import GmailAuthenticator
from email_preprocessing.pipelines.preprocessing.cleaner import clean_text, html_to_text
from email_preprocessing.pipelines.preprocessing.parser import (
    extract_email_metadata,
    process_email_content,
)
from email_preprocessing.services.gmail_service import GmailService
from email_preprocessing.services.storage_service import StorageService


class EmailPipeline:
    def __init__(self, db_session, email_address, client_config):
        self.email_address = email_address
        self.authenticator = GmailAuthenticator(db_session)
        self.credentials = self.authenticator.authenticate(email_address, client_config)
        if self.credentials:
            self.gmail_service = GmailService(self.credentials)
            self.storage_service = StorageService()
        else:
            raise Exception("Failed to authenticate Gmail")

    def process_emails(self, start_date, end_date=None):
        try:
            messages = self.gmail_service.list_emails(start_date, end_date)
            if not messages:
                return 0, 0

            successful_saves = 0
            for message in messages:
                try:
                    raw_msg = self.gmail_service.get_email(message["id"])
                    if raw_msg and self.storage_service.save_email(
                        self.email_address, message["id"], raw_msg
                    ):
                        successful_saves += 1
                except Exception as e:
                    logging.error(f"Error storing raw message {message['id']}: {e}")
                    continue

            return len(messages), successful_saves
        except Exception as e:
            logging.error(f"Error in store_raw_emails: {e}")
            return 0, 0

    def process_threads(self, start_date, end_date=None):
        """Store raw threads in GCS without preprocessing."""
        try:
            threads = self.gmail_service.list_threads(start_date, end_date)
            if not threads:
                return 0, 0

            successful_saves = 0
            for thread in threads:
                try:
                    thread_data = self.gmail_service.get_thread(thread["id"])
                    if thread_data and self.storage_service.save_thread(
                        self.email_address, thread["id"], thread_data
                    ):
                        successful_saves += 1
                except Exception as e:
                    logging.error(f"Error storing raw thread {thread['id']}: {e}")
                    continue

            return len(threads), successful_saves
        except Exception as e:
            logging.error(f"Error in store_raw_threads: {e}")
            return 0, 0
