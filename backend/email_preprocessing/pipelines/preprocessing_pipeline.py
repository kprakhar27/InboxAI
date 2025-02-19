import logging
from datetime import datetime
from email import policy
from email.parser import BytesParser

from email_preprocessing.pipelines.preprocessing.cleaner import clean_text
from email_preprocessing.pipelines.preprocessing.parser import (
    extract_email_metadata,
    process_email_content,
)
from email_preprocessing.services.storage_service import StorageService
from email_preprocessing.utils.db_handler import (
    add_preprocessing_summary,
    fetch_ready_for_processing,
    get_session,
    update_processing_status,
)


class PreprocessingPipeline:
    """Pipeline for preprocessing raw emails/threads from GCS."""

    def __init__(self, email):
        self.storage_service = StorageService()
        self.email = email
        self.db_session = get_session()

    def process_ready_items(self):
        """Process all items that are ready for preprocessing."""
        stats = {
            "email": {"processed": 0, "failed": 0, "total": 0},
            "thread": {"processed": 0, "failed": 0, "total": 0},
            "timestamp": datetime.now().isoformat(),
        }
        try:
            ready_items = fetch_ready_for_processing(self.db_session, email=self.email)
            for item in ready_items:
                if item.item_type == "emails":
                    raw_path = f"emails/raw/{item.email}/{item.raw_to_gcs_timestamp.strftime('%m%d%Yat%H%M')}/"
                    cleaned_path = f"emails/cleaned/{item.email}/{item.raw_to_gcs_timestamp.strftime('%m%d%Yat%H%M')}/"
                    raw_files = self.storage_service.list_files(raw_path)
                    stats["email"]["total"] += len(raw_files)
                    all_success = True
                    for raw_file in raw_files:
                        cleaned_file_path = f"{cleaned_path}{raw_file.split('/')[-1]}"
                        cleaned_file_path = cleaned_file_path[:-4] + ".json"
                        success = self.process_raw_email(raw_file, cleaned_file_path)
                        if not success:
                            all_success = False
                            stats["email"]["failed"] += 1
                        else:
                            stats["email"]["processed"] += 1
                    if all_success:
                        update_processing_status(
                            self.db_session, item.run_id, "success"
                        )
                    else:
                        update_processing_status(self.db_session, item.run_id, "failed")
                elif item.item_type == "threads":
                    raw_path = f"threads/raw/{item.email}/{item.raw_to_gcs_timestamp.strftime('%m%d%Yat%H%M')}/"
                    cleaned_path = f"threads/cleaned/{item.email}/{item.raw_to_gcs_timestamp.strftime('%m%d%Yat%H%M')}/"
                    raw_files = self.storage_service.list_files(raw_path)
                    stats["thread"]["total"] += len(raw_files)
                    all_success = True
                    for raw_file in raw_files:
                        cleaned_file_path = f"{cleaned_path}{raw_file.split('/')[-1]}"
                        success = self.process_raw_thread(raw_file, cleaned_file_path)
                        if not success:
                            all_success = False
                            stats["thread"]["failed"] += 1
                        else:
                            stats["thread"]["processed"] += 1
                    if all_success:
                        update_processing_status(
                            self.db_session, item.run_id, "success"
                        )
                    else:
                        update_processing_status(self.db_session, item.run_id, "failed")
            logging.info(f"Processing Summary: {stats}")
            if add_preprocessing_summary(
                self.db_session,
                self.email,
                stats["email"]["total"],
                stats["thread"]["total"],
                stats["email"]["processed"],
                stats["thread"]["processed"],
                stats["email"]["failed"],
                stats["thread"]["failed"],
            ):
                logging.info("Committed preprocessing summary to the database")
            else:
                logging.error("Failed to commit preprocessing summary to the database")

            return stats
        except Exception as e:
            logging.error(f"Error processing ready items: {e}")
            return stats

    def process_raw_email(self, raw_email_path, processed_email_path):
        """Process a single raw email and store the processed version."""
        try:
            # Fetch raw email from GCS
            raw_data = self.storage_service.get_raw_email(raw_email_path)
            if not raw_data:
                return False

            # Decode raw email to string to be able to process it
            email_message = BytesParser(policy=policy.default).parsebytes(raw_data)

            # Preprocess
            processed_data = self._preprocess_email(email_message)
            if not processed_data:
                return False

            # Store processed data
            return self.storage_service.save_processed_email(
                processed_email_path, processed_data
            )
        except Exception as e:
            logging.error(f"Error processing email {raw_email_path}: {e}")
            return False

    def process_raw_thread(self, raw_thread_path, processed_thread_path):
        """Process a single raw thread and store the processed version."""
        try:
            # Fetch raw thread from GCS
            raw_data = self.storage_service.get_raw_thread(raw_thread_path)
            if not raw_data:
                return False

            thread_message = BytesParser(policy=policy.default).parsebytes(raw_data)

            # Preprocess
            processed_data = self._preprocess_thread(thread_message)
            if not processed_data:
                return False

            # Store processed data
            return self.storage_service.save_processed_thread(
                processed_thread_path, processed_data
            )
        except Exception as e:
            logging.error(f"Error processing thread {raw_thread_path}: {e}")
            return False

    def _preprocess_email(self, raw_data):
        """Preprocess a single email."""
        metadata = extract_email_metadata(raw_data)
        content, attachments = process_email_content(raw_data)
        cleaned_content = clean_text(content)

        return {
            "metadata": metadata,
            "content": cleaned_content,
            "attachments": attachments,
            "processing_info": {
                "processed_timestamp": datetime.now().isoformat(),
                "content_length": len(cleaned_content),
                "has_attachments": bool(attachments),
            },
        }

    def _preprocess_thread(self, raw_data):
        """Preprocess a thread and all its messages."""
        processed_messages = []
        for message in raw_data.get("messages", []):
            processed_message = self._preprocess_email(message)
            if processed_message:
                processed_messages.append(processed_message)

        return {
            "thread_id": raw_data.get("id"),
            "messages": processed_messages,
            "processing_info": {
                "processed_timestamp": datetime.now().isoformat(),
                "message_count": len(processed_messages),
            },
        }
