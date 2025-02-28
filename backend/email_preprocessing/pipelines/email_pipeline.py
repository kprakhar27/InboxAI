import logging
from collections import defaultdict
from datetime import datetime, timezone

from email_preprocessing.auth.gmail_auth import GmailAuthenticator
from email_preprocessing.services.gmail_service import GmailService
from email_preprocessing.services.storage_service import StorageService
from email_preprocessing.utils.db_handler import (
    add_processing_summary,
    add_unique_timestamps,
    get_last_read_timestamp,
    get_session,
    update_last_read_timestamp,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class EmailPipeline:
    def __init__(self, email_address, client_config):
        self.email_address = email_address
        self.db_session = get_session()
        self.authenticator = GmailAuthenticator(self.db_session)
        self.credentials = self.authenticator.authenticate(email_address, client_config)
        if self.credentials:
            self.gmail_service = GmailService(self.credentials)
            self.storage_service = StorageService()
            logging.info(f"Authenticated Gmail for {email_address}")
        else:
            logging.error("Failed to authenticate Gmail")
            raise Exception("Failed to authenticate Gmail")

    def process_items(self):
        try:
            start_date = get_last_read_timestamp(self.db_session, self.email_address)
            end_date = datetime.now(timezone.utc)

            item_types = ["emails", "threads"]
            results = {}
            timestamp_email_map = defaultdict(set)

            total_emails_processed = 0
            total_threads_processed = 0
            failed_emails = 0
            failed_threads = 0

            for item_type in item_types:
                if item_type == "emails":
                    items = self.gmail_service.list_emails(start_date, end_date)
                    get_item = self.gmail_service.get_email
                    save_item = self.storage_service.save_raw_email
                elif item_type == "threads":
                    items = self.gmail_service.list_threads(start_date, end_date)
                    get_item = self.gmail_service.get_thread
                    save_item = self.storage_service.save_raw_thread

                if not items:
                    results[item_type] = {
                        "total": 0,
                        "successful": 0,
                        "timestamps": [start_date, end_date],
                    }
                    logging.info(f"No {item_type} found for processing.")
                    continue

                successful_saves = 0
                for item in items:
                    try:
                        item_data = get_item(item["id"])
                        if item_data:
                            now = datetime.now().strftime("%m%d%Yat%H%M")
                            if save_item(self.email_address, item["id"], item_data):
                                successful_saves += 1
                                logging.info(
                                    f"Successfully saved {item_type[:-1]} {item['id']}"
                                )
                                # Collect unique timestamp and email address
                                timestamp_email_map[now].add(
                                    (self.email_address, item_type)
                                )
                    except Exception as e:
                        logging.error(
                            f"Error storing raw {item_type[:-1]} {item['id']}: {e}"
                        )
                        if item_type == "emails":
                            failed_emails += 1
                        elif item_type == "threads":
                            failed_threads += 1
                        continue

                if item_type == "emails":
                    total_emails_processed += len(items)
                elif item_type == "threads":
                    total_threads_processed += len(items)

                results[item_type] = {
                    "total": len(items),
                    "successful": successful_saves,
                    "timestamps": [start_date, end_date],
                }
                logging.info(f"Processed {item_type}: {results[item_type]}")

            # Commit collected unique timestamps and email addresses to the database
            if add_unique_timestamps(self.db_session, timestamp_email_map):
                logging.info(
                    "Committed ready for preprocessing email records to the database"
                )
            else:
                logging.error("Failed to commit email records to the database")

            update_last_read_timestamp(
                self.db_session, self.email_address, start_date, end_date
            )
            logging.info(
                f"Updated last read timestamp for {self.email_address} to {end_date}"
            )
            logging.info(f"results: {results}")

            # Add processing summary to the database
            if add_processing_summary(
                self.db_session,
                self.email_address,
                total_emails_processed,
                total_threads_processed,
                failed_emails,
                failed_threads,
            ):
                logging.info("Committed processing summary to the database")
            else:
                logging.error("Failed to commit processing summary to the database")

            return results
        except Exception as e:
            logging.error(f"Error in process_items: {e}")
            return {
                "emails": {
                    "total": 0,
                    "successful": 0,
                    "timestamps": [None, None],
                },
                "threads": {
                    "total": 0,
                    "successful": 0,
                    "timestamps": [None, None],
                },
            }

    def process_items_batch(self):
        try:
            start_date = get_last_read_timestamp(self.db_session, self.email_address)
            end_date = datetime.now(timezone.utc)

            item_types = ["emails", "threads"]
            results = {}
            timestamp_email_map = defaultdict(set)

            total_emails_processed = 0
            total_threads_processed = 0
            failed_emails = 0
            failed_threads = 0

            for item_type in item_types:
                # List all items (emails or threads)
                if item_type == "emails":
                    items = self.gmail_service.list_emails(
                        start_date, end_date, maxResults=500
                    )
                    get_items_batch = self.gmail_service.get_emails_batch
                    save_items_batch = self.storage_service.save_raw_emails_batch
                else:
                    items = self.gmail_service.list_threads(
                        start_date, end_date, maxResults=500
                    )
                    get_items_batch = self.gmail_service.get_threads_batch
                    save_items_batch = self.storage_service.save_raw_threads_batch

                if not items:
                    results[item_type] = {
                        "total": 0,
                        "successful": 0,
                        "timestamps": [start_date, end_date],
                    }
                    logging.info(f"No {item_type} found for processing.")
                    continue

                # Process items in batches
                batch_size = 100
                for i in range(0, len(items), batch_size):
                    batch_items = items[i : i + batch_size]
                    batch_ids = [item["id"] for item in batch_items]

                    try:
                        # Fetch batch of items
                        items_data = get_items_batch(batch_ids)
                        if items_data:
                            now = datetime.now().strftime("%m%d%Yat%H%M")

                            # Save batch of items
                            saved_paths = save_items_batch(
                                self.email_address, items_data
                            )

                            if saved_paths:
                                successful_saves = len(saved_paths)
                                logging.info(
                                    f"Successfully saved batch of {successful_saves} {item_type}"
                                )

                                # Update timestamp mapping
                                for item_id in saved_paths:
                                    timestamp_email_map[now].add(
                                        (self.email_address, item_type)
                                    )

                            if item_type == "emails":
                                total_emails_processed += len(batch_items)
                                failed_emails += len(batch_items) - len(saved_paths)
                            else:
                                total_threads_processed += len(batch_items)
                                failed_threads += len(batch_items) - len(saved_paths)

                    except Exception as e:
                        logging.error(f"Error processing batch of {item_type}: {e}")
                        if item_type == "emails":
                            failed_emails += len(batch_items)
                        else:
                            failed_threads += len(batch_items)

                results[item_type] = {
                    "total": len(items),
                    "successful": (
                        total_emails_processed
                        if item_type == "emails"
                        else total_threads_processed
                    ),
                    "timestamps": [start_date, end_date],
                }
                logging.info(f"Processed {item_type}: {results[item_type]}")

            # Commit collected unique timestamps and email addresses to the database
            if add_unique_timestamps(self.db_session, timestamp_email_map):
                logging.info(
                    "Committed ready for preprocessing email records to the database"
                )
            else:
                logging.error("Failed to commit email records to the database")

            update_last_read_timestamp(
                self.db_session, self.email_address, start_date, end_date
            )
            logging.info(
                f"Updated last read timestamp for {self.email_address} to {end_date}"
            )
            logging.info(f"results: {results}")

            # Add processing summary to the database
            if add_processing_summary(
                self.db_session,
                self.email_address,
                total_emails_processed,
                total_threads_processed,
                failed_emails,
                failed_threads,
            ):
                logging.info("Committed processing summary to the database")
            else:
                logging.error("Failed to commit processing summary to the database")

            return results
        except Exception as e:
            logging.error(f"Error in process_items: {e}")
            return {
                "emails": {"total": 0, "successful": 0, "timestamps": [None, None]},
                "threads": {"total": 0, "successful": 0, "timestamps": [None, None]},
            }
