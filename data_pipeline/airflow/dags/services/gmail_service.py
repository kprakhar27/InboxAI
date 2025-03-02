import logging
import time
from datetime import datetime, timezone
from email.utils import parseaddr

from airflow.exceptions import AirflowException
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from models_pydantic import EmailSchema
from pydantic import ValidationError

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class GmailService:
    def __init__(self, credentials):
        self.service = build("gmail", "v1", credentials=credentials)
        logging.info("Gmail service initialized")

    def list_emails(self, start_timestamp, end_timestamp=None, maxResults=10):
        """
        List emails between timestamps with improved error handling for Airflow
        """
        start_date = int(start_timestamp.timestamp())
        end_date = int(end_timestamp.timestamp()) if end_timestamp else None

        logging.info(f"Listing emails from {start_date} to {end_date}")

        query = f"after:{start_date}"
        if end_timestamp:
            query += f" before:{end_date}"

        messages = []
        page_token = None

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
                    .execute()
                )

                if "messages" in results:
                    messages.extend(results["messages"])

                page_token = results.get("nextPageToken")
                if not page_token:
                    break

                # Add small delay to respect rate limits
                time.sleep(60 / 15000)

            except HttpError as e:
                if e.resp.status == 429:  # Rate limit exceeded
                    raise AirflowException("Rate limit exceeded - Airflow will retry")
                logging.error(f"Error fetching messages: {e}")
                raise

        logging.info(f"Fetched {len(messages)} messages")
        return messages

    def get_emails_batch(self, msg_ids, batch_size=10):
        """
        Fetch multiple emails in batches with improved error handling
        """
        logging.info(f"Fetching {len(msg_ids)} emails in batches of {batch_size}")
        emails = {}

        def callback(request_id, response, exception):
            if exception is None:
                try:
                    # Transform and validate email using Pydantic
                    email_data = transform_email_data(response)
                    validated_email = EmailSchema(**email_data)
                    emails[request_id] = validated_email.dict()
                except ValidationError as e:
                    logging.error(f"Validation error for email {request_id}: {e}")
                    emails[request_id] = None
            elif isinstance(exception, HttpError) and exception.resp.status == 429:
                # Propagate rate limit errors to allow Airflow retry
                raise AirflowException(
                    "Rate limit exceeded in batch - Airflow will retry"
                )
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
                    .get(userId="me", id=msg_id, format="full"),
                    request_id=msg_id,
                )

            retries = 0
            while retries < 5:
                try:
                    batch.execute()
                    logging.info(f"Processed batch of {len(batch_ids)} emails")
                    # Add small delay between batches
                    time.sleep(2)
                    break
                except HttpError as e:
                    if e.resp.status == 429:
                        retries += 1
                        wait_time = 2**retries
                        logging.warning(
                            f"Rate limit exceeded, retrying in {wait_time} seconds..."
                        )
                        time.sleep(wait_time)
                    else:
                        raise
            else:
                raise AirflowException("Rate limit exceeded - Max retries reached")

        return emails

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
                    )
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


def is_valid_email(email):
    """Check if the email address is valid."""
    return "@" in parseaddr(email)[1]


def extract_email_address(header_value):
    """Extract email address from header value that may include display name."""
    if not header_value:
        return None
    # Handle multiple email addresses
    if "," in header_value:
        addresses = header_value.split(",")
        return [
            parseaddr(addr.strip())[1]
            for addr in addresses
            if parseaddr(addr.strip())[1]
        ]
    return parseaddr(header_value)[1]


def transform_email_data(raw_email):
    """Transform raw email data into structured format with content extraction."""
    payload = raw_email.get("payload", {})
    headers = {header["name"]: header["value"] for header in payload.get("headers", [])}

    # Extract email content
    plain_text = None
    html = None

    def extract_content(parts):
        """Recursively extract content from email parts."""
        nonlocal plain_text, html
        if not parts:
            return

        for part in parts:
            mime_type = part.get("mimeType", "")
            # Get body data
            body_data = None
            body = part.get("body", {})

            if body.get("data"):
                body_data = body["data"]
            elif body.get("attachmentId"):
                # Handle attachment if needed
                continue

            # Extract content based on mime type
            if "text/plain" in mime_type and not plain_text:
                plain_text = body_data
            elif "text/html" in mime_type and not html:
                html = body_data

            # Handle nested multipart messages
            if part.get("parts"):
                extract_content(part["parts"])

    # First try to extract from parts
    parts = payload.get("parts", [])
    extract_content(parts)

    # If no content found, try body directly
    if not plain_text and not html:
        body = payload.get("body", {}).get("data")
        mime_type = payload.get("mimeType", "")
        if body:
            if "text/plain" in mime_type:
                plain_text = body
            elif "text/html" in mime_type:
                html = body

    # Process recipients
    to_addresses = headers.get("To", "").split(",") if headers.get("To") else []
    cc_addresses = headers.get("Cc", "").split(",") if headers.get("Cc") else None
    bcc_addresses = headers.get("Bcc", "").split(",") if headers.get("Bcc") else None

    # Clean addresses
    to_addresses = [addr.strip() for addr in to_addresses if addr.strip()]
    if cc_addresses:
        cc_addresses = [addr.strip() for addr in cc_addresses if addr.strip()]
    if bcc_addresses:
        bcc_addresses = [addr.strip() for addr in bcc_addresses if addr.strip()]

    email_data = {
        "message_id": raw_email.get("id"),
        "from_email": headers.get("From", "").strip(),
        "to": to_addresses,
        "cc": cc_addresses,
        "bcc": bcc_addresses,
        "subject": headers.get("Subject", ""),
        "date": datetime.fromtimestamp(
            int(raw_email.get("internalDate", 0)) / 1000, tz=timezone.utc
        ).isoformat(),
        "plain_text": plain_text,
        "html": html,
        "thread_id": raw_email.get("threadId"),
        "labels": raw_email.get("labelIds", []),
        "attachments": [],  # Will be populated if needed
    }

    # Add attachments if present
    if parts:
        for part in parts:
            if part.get("filename"):
                email_data["attachments"].append(
                    {
                        "filename": part["filename"],
                        "mime_type": part.get("mimeType", ""),
                        "size": part.get("body", {}).get("size"),
                    }
                )

    return email_data
