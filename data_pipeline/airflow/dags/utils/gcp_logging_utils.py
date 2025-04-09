import json
import logging

import google.cloud.logging
from google.cloud.logging.handlers import CloudLoggingHandler


def setup_gcp_logging(module_name):
    """
    Set up Google Cloud Logging for the specified module.

    Args:
        module_name (str): Name of the module for identification in logs

    Returns:
        logging.Logger: Configured logger instance
    """
    try:
        # Create a Cloud Logging client
        client = google.cloud.logging.Client()

        # Create a cloud logging handler
        handler = CloudLoggingHandler(client, name="inboxai")

        # Create a structured formatter
        class StructuredFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    "timestamp": self.formatTime(record),
                    "severity": record.levelname,
                    "application": "inboxai",
                    "module": module_name,
                    "message": record.getMessage(),
                    "function": record.funcName,
                    "line": record.lineno,
                }

                # Add exception info if present
                if record.exc_info:
                    log_entry["exception"] = self.formatException(record.exc_info)

                return json.dumps(log_entry)

        # Apply the formatter to the handler
        handler.setFormatter(StructuredFormatter())

        # Get the logger and set level
        logger = logging.getLogger(module_name)
        logger.setLevel(logging.INFO)

        # Make sure we don't duplicate handlers
        if not any(isinstance(h, CloudLoggingHandler) for h in logger.handlers):
            logger.addHandler(handler)

        return logger

    except Exception as e:
        # Fallback to standard logging if GCP setup fails
        fallback_logger = logging.getLogger(module_name)
        fallback_logger.warning(
            f"Failed to set up GCP logging: {str(e)}. Using standard logging."
        )
        return fallback_logger
