import logging
from datetime import datetime

from preprocessing.cleaner import clean_text
from preprocessing.parser import extract_email_metadata, process_email_content
from services.storage_service import StorageService


class PreprocessingPipeline:
    """Pipeline for preprocessing raw emails/threads from GCS."""

    def __init__(self):
        self.storage_service = StorageService()

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
