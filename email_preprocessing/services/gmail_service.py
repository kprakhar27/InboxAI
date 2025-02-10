import logging

from googleapiclient.discovery import build


class GmailService:
    def __init__(self, credentials):
        self.service = build("gmail", "v1", credentials=credentials)

    def list_emails(self, start_timestamp, end_timestamp=None):
        query = f"after:{start_timestamp}"
        if end_timestamp:
            query += f" before:{end_timestamp}"

        messages = []
        page_token = None

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

        return messages

    def list_threads(self, start_timestamp, end_timestamp=None):
        query = f"after:{start_timestamp}"
        if end_timestamp:
            query += f" before:{end_timestamp}"

        threads = []
        page_token = None

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

        return threads

    def get_email(self, msg_id):
        try:
            return (
                self.service.users()
                .messages()
                .get(userId="me", id=msg_id, format="raw")
                .execute()
            )
        except Exception as e:
            logging.error(f"Error getting email {msg_id}: {e}")
            return None

    def get_thread(self, thread_id):
        try:
            return (
                self.service.users().threads().get(userId="me", id=thread_id).execute()
            )
        except Exception as e:
            logging.error(f"Error getting thread {thread_id}: {e}")
            return None
