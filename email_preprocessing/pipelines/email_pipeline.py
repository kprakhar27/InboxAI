import json
import logging
from datetime import datetime
from email import policy
from email.parser import BytesParser

from auth.gmail_auth import GmailAuthenticator
from preprocessing.cleaner import clean_text, html_to_text
from preprocessing.parser import extract_email_metadata, process_email_content
from services.gmail_service import GmailService
from services.storage_service import StorageService


class EmailPipeline:
    def __init__(self, email_address):
        self.email_address = email_address
        self.credentials = GmailAuthenticator.authenticate(email_address)
        if self.credentials:
            self.gmail_service = GmailService(self.credentials)
            self.storage_service = StorageService()
        else:
            raise Exception("Failed to authenticate Gmail")

    def process_emails(self, start_date, end_date=None):
        messages = self.gmail_service.list_emails(start_date, end_date)
        if not messages:
            return 0, 0

        successful_saves = 0
        for message in messages:
            raw_msg = self.gmail_service.get_email(message["id"])
            if raw_msg and self.storage_service.save_email(
                self.email_address, message["id"], raw_msg
            ):
                successful_saves += 1

        return len(messages), successful_saves

    def process_threads(self, start_date, end_date=None):
        threads = self.gmail_service.list_threads(start_date, end_date)
        if not threads:
            return 0, 0

        successful_saves = 0
        for thread in threads:
            thread_data = self.gmail_service.get_thread(thread["id"])
            if thread_data and self.storage_service.save_thread(
                self.email_address, thread["id"], thread_data
            ):
                successful_saves += 1

        return len(threads), successful_saves

    def _clean_and_process_email(self, raw_msg, message_id):
        """Process and clean a single email message."""
        msg = BytesParser(policy=policy.default).parsebytes(raw_msg)

        # Extract metadata and content
        metadata = extract_email_metadata(msg)
        content, attachments = process_email_content(msg)

        # Prepare processed data
        return {
            "metadata": metadata,
            "content": content,
            "attachments": attachments,
            "processing_info": {
                "message_id": message_id,
                "processed_timestamp": datetime.now().isoformat(),
                "content_length": len(content),
            },
        }

    def _clean_thread(self, thread_data, thread_id):
        """Process and clean an entire email thread."""
        cleaned_messages = []

        for message in thread_data.get("messages", []):
            try:
                cleaned_message = self._clean_and_process_email(
                    message["raw"], message["id"]
                )
                cleaned_messages.append(cleaned_message)
            except Exception as e:
                logging.error(
                    f"Error cleaning message {message['id']} in thread {thread_id}: {e}"
                )

        return {
            "thread_id": thread_id,
            "messages": cleaned_messages,
            "processing_info": {
                "processed_timestamp": datetime.now().isoformat(),
                "message_count": len(cleaned_messages),
            },
        }
