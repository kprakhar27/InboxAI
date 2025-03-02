import logging
from googleapiclient.discovery import build
from googleapiclient.http import BatchHttpRequest


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class GmailService:
    def __init__(self, credentials):
        self.service = build("gmail", "v1", credentials=credentials)
        logging.info("Gmail service initialized")

    def list_emails(self, start_timestamp, end_timestamp=None, maxResults=500):
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
                    .list(
                        userId="me",
                        q=query,
                        pageToken=page_token,
                        maxResults=maxResults,
                    )

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

    def list_threads(self, start_timestamp, end_timestamp=None, maxResults=500):
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
                    .list(
                        userId="me",
                        q=query,
                        pageToken=page_token,
                        maxResults=maxResults,
                    ).execute()
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

    def get_emails_batch(self, msg_ids, batch_size=100):
        """Fetch multiple emails in batches"""
        logging.info(f"Fetching {len(msg_ids)} emails in batches of {batch_size}")
        emails = {}

        def callback(request_id, response, exception):
            if exception is None:
                emails[request_id] = response
            else:
                logging.error(f"Error fetching email {request_id}: {exception}")
                emails[request_id] = None

        for i in range(0, len(msg_ids), batch_size):
            batch = self.service.new_batch_http_request(callback=callback)
            batch_ids = msg_ids[i : i + batch_size]

            for msg_id in batch_ids:
                batch.add(
                    self.service.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="raw"),
                    request_id=msg_id,
                )

            batch.execute()
            logging.info(f"Processed batch of {len(batch_ids)} emails")

        return emails

    def get_threads_batch(self, thread_ids, batch_size=100):
        """Fetch multiple threads in batches"""
        logging.info(f"Fetching {len(thread_ids)} threads in batches of {batch_size}")
        threads = {}

        def callback(request_id, response, exception):
            if exception is None:
                threads[request_id] = response
            else:
                logging.error(f"Error fetching thread {request_id}: {exception}")
                threads[request_id] = None

        for i in range(0, len(thread_ids), batch_size):
            batch = self.service.new_batch_http_request(callback=callback)
            batch_ids = thread_ids[i : i + batch_size]

            for thread_id in batch_ids:
                batch.add(
                    self.service.users().threads().get(userId="me", id=thread_id),
                    request_id=thread_id,
                )

            batch.execute()
            logging.info(f"Processed batch of {len(batch_ids)} threads")

        return threads
