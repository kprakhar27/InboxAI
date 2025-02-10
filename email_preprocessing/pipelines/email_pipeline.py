import logging
from datetime import datetime

from auth.gmail_auth import GmailAuthenticator
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
