import logging

from pipelines.email_pipeline import EmailPipeline


def run_pipeline(email_address, start_date, end_date=None):
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    try:
        pipeline = EmailPipeline(email_address)

        # Process emails
        total_emails, saved_emails = pipeline.process_emails(start_date, end_date)
        logging.info(
            f"Email processing completed: Total: {total_emails}, "
            f"Saved: {saved_emails}, Failed: {total_emails - saved_emails}"
        )

        # Process threads
        total_threads, saved_threads = pipeline.process_threads(start_date, end_date)
        logging.info(
            f"Thread processing completed: Total: {total_threads}, "
            f"Saved: {saved_threads}, Failed: {total_threads - saved_threads}"
        )

        return {
            "emails": {"total": total_emails, "saved": saved_emails},
            "threads": {"total": total_threads, "saved": saved_threads},
        }
    except Exception as e:
        logging.error(f"Pipeline failed: {e}")
        return None


if __name__ == "__main__":
    email_address = "pc612001@gmail.com"
    run_pipeline(email_address, "2025/02/01", "2025/02/10")
