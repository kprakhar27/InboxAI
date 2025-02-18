import logging
from datetime import datetime

from email_preprocessing.pipelines.preprocessing.cleaner import clean_text
from email_preprocessing.pipelines.preprocessing.parser import (
    extract_email_metadata,
    process_email_content,
)
from email_preprocessing.services.storage_service import StorageService
from email_preprocessing.utils.db_handler import (
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
        try:
            ready_items = fetch_ready_for_processing(self.db_session, email=self.email)
            for item in ready_items:
                if item.item_type == "email":
                    raw_path = f"emails/raw/{item.email}/{item.raw_to_gcs_timestamp.strftime('%m%d%Yat%H%M')}/"
                    cleaned_path = f"emails/cleaned/{item.email}/{item.raw_to_gcs_timestamp.strftime('%m%d%Yat%H%M')}/cleaned_{item.run_id}.eml"
                    raw_files = self.storage_service.list_files(raw_path)
                    for raw_file in raw_files:
                        success = self.process_raw_email(raw_file, cleaned_path)
                        if success:
                            update_processing_status(
                                self.db_session, item.run_id, "processed"
                            )
                        else:
                            update_processing_status(
                                self.db_session, item.run_id, "failed"
                            )
                elif item.item_type == "thread":
                    raw_path = f"threads/raw/{item.email}/{item.raw_to_gcs_timestamp.strftime('%m%d%Yat%H%M')}/"
                    cleaned_path = f"threads/cleaned/{item.email}/{item.raw_to_gcs_timestamp.strftime('%m%d%Yat%H%M')}/cleaned_{item.run_id}.json"
                    raw_files = self.storage_service.list_files(raw_path)
                    for raw_file in raw_files:
                        success = self.process_raw_thread(raw_file, cleaned_path)
                        if success:
                            update_processing_status(
                                self.db_session, item.run_id, "processed"
                            )
                        else:
                            update_processing_status(
                                self.db_session, item.run_id, "failed"
                            )
        except Exception as e:
            logging.error(f"Error processing ready items: {e}")

    def process_raw_email(self, raw_email_path, processed_email_path):
        """Process a single raw email and store the processed version."""
        try:
            # Fetch raw email from GCS
            raw_data = self.storage_service.get_raw_email(raw_email_path)
            if not raw_data:
                return False

            # Preprocess
            processed_data = self._preprocess_email(raw_data)
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

            # Preprocess
            processed_data = self._preprocess_thread(raw_data)
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
        try:
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
        except Exception as e:
            logging.error(f"Error preprocessing email: {e}")
            return None

    def _preprocess_thread(self, raw_data):
        """Preprocess a thread and all its messages."""
        try:
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
        except Exception as e:
            logging.error(f"Error preprocessing thread: {e}")
            return None
