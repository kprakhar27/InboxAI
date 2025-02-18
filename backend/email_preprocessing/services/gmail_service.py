import logging

from googleapiclient.discovery import build

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class GmailService:
    def __init__(self, credentials):
        self.service = build("gmail", "v1", credentials=credentials)
        logging.info("Gmail service initialized")

    def list_emails(self, start_timestamp, end_timestamp=None):
        start_date = int(start_timestamp.timestamp())
        end_date = int(end_timestamp.timestamp()) if end_timestamp else None

        logging.info(f"Listing emails from {start_date} to {end_date}")

        query = f"after:{start_date}"
        if end_timestamp:
            query += f" before:{end_date}"

        messages = []
        page_token = None

        logging.info(f"Listing emails with query: {query}")

        while True:
            try:
                results = (
                    self.service.users()
                    .messages()
                    .list(userId="me", q=query, pageToken=page_token)
                    .execute()
                )
                messages.extend(results.get("messages", []))
                page_token = results.get("nextPageToken")
                if not page_token:
                    break
            except Exception as e:
                logging.error(f"Error fetching messages: {e}")
                break

        logging.info(f"Fetched {len(messages)} messages")
        return messages

    def list_threads(self, start_timestamp, end_timestamp=None):
        start_date = int(start_timestamp.timestamp())
        end_date = int(end_timestamp.timestamp()) if end_timestamp else None

        query = f"after:{start_date}"
        if end_timestamp:
            query += f" before:{end_date}"

        threads = []
        page_token = None

        logging.info(f"Listing threads with query: {query}")

        while True:
            try:
                results = (
                    self.service.users()
                    .threads()
                    .list(userId="me", q=query, pageToken=page_token)
                    .execute()
                )
                threads.extend(results.get("threads", []))
                page_token = results.get("nextPageToken")
                if not page_token:
                    break
            except Exception as e:
                logging.error(f"Error fetching threads: {e}")
                break

        logging.info(f"Fetched {len(threads)} threads")
        return threads

    def get_email(self, msg_id):
        logging.info(f"Getting email with ID: {msg_id}")
        try:
            email = (
                self.service.users()
                .messages()
                .get(userId="me", id=msg_id, format="raw")
                .execute()
            )
            logging.info(f"Email with ID {msg_id} fetched successfully")
            return email
        except Exception as e:
            logging.error(f"Error getting email {msg_id}: {e}")
            return None

    def get_thread(self, thread_id):
        logging.info(f"Getting thread with ID: {thread_id}")
        try:
            thread = (
                self.service.users().threads().get(userId="me", id=thread_id).execute()
            )
            logging.info(f"Thread with ID {thread_id} fetched successfully")
            return thread
        except Exception as e:
            logging.error(f"Error getting thread {thread_id}: {e}")
            return None
