import json
import logging
import os
from datetime import datetime
from typing import Dict, Optional

from google.cloud import storage


class PreprocessingPipeline:
    def __init__(self, source_bucket: str, dest_bucket: str):
        self.storage_client = storage.Client()
        self.source_bucket = self.storage_client.bucket(source_bucket)
        self.dest_bucket = self.storage_client.bucket(dest_bucket)

    def process_raw_emails(self, email_address: str, batch_size: int = 100) -> Dict:
        """Process raw emails for a specific email address."""
        prefix = f"raw_emails/{email_address}/"
        blobs = list(
            self.source_bucket.list_blobs(prefix=prefix, max_results=batch_size)
        )

        processed = 0
        failed = 0

        for blob in blobs:
            try:
                result = self.process_single_email(blob, email_address)
                if result["success"]:
                    processed += 1
                else:
                    failed += 1
            except Exception as e:
                logging.error(f"Failed to process {blob.name}: {e}")
                failed += 1

        return {"total": len(blobs), "processed": processed, "failed": failed}

    def process_raw_threads(self, email_address: str, batch_size: int = 100) -> Dict:
        """Process raw email threads for a specific email address."""
        prefix = f"raw_threads/{email_address}/"
        blobs = list(
            self.source_bucket.list_blobs(prefix=prefix, max_results=batch_size)
        )

        processed = 0
        failed = 0

        for blob in blobs:
            try:
                result = self.process_single_thread(blob, email_address)
                if result["success"]:
                    processed += 1
                else:
                    failed += 1
            except Exception as e:
                logging.error(f"Failed to process thread {blob.name}: {e}")
                failed += 1

        return {"total": len(blobs), "processed": processed, "failed": failed}


def run_pipeline(
    email_address: str,
    source_bucket: str = os.environ.get("RAW_BUCKET_NAME"),
    dest_bucket: str = os.environ.get("PROCESSED_BUCKET_NAME"),
    batch_size: int = 100,
) -> Optional[Dict]:
    """
    Run the preprocessing pipeline on stored raw emails and threads.

    Args:
        email_address: Email address to process
        source_bucket: Name of bucket containing raw emails
        dest_bucket: Name of bucket for processed emails
        batch_size: Number of items to process in one batch

    Returns:
        Dictionary with processing statistics or None if failed
    """
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    try:
        pipeline = PreprocessingPipeline(source_bucket, dest_bucket)

        # Process raw emails
        email_stats = pipeline.process_raw_emails(email_address, batch_size)
        logging.info(
            f"Email preprocessing completed: Total: {email_stats['total']}, "
            f"Processed: {email_stats['processed']}, Failed: {email_stats['failed']}"
        )

        # Process raw threads
        thread_stats = pipeline.process_raw_threads(email_address, batch_size)
        logging.info(
            f"Thread preprocessing completed: Total: {thread_stats['total']}, "
            f"Processed: {thread_stats['processed']}, Failed: {thread_stats['failed']}"
        )

        return {
            "emails": email_stats,
            "threads": thread_stats,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logging.error(f"Preprocessing pipeline failed: {e}")
        return None


if __name__ == "__main__":
    # Example usage
    results = run_pipeline(
        email_address="user@example.com",
        source_bucket="raw-emails-bucket",
        dest_bucket="processed-emails-bucket",
        batch_size=100,
    )

    if results:
        print(json.dumps(results, indent=2))
