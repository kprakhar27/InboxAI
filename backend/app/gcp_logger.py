import json
import logging
import os
from datetime import datetime
from functools import wraps
from typing import Callable

import google.cloud.logging
from dotenv import load_dotenv
from flask import current_app, request
from google.cloud.logging.handlers import CloudLoggingHandler

# Load environment variables
load_dotenv()


def setup_gcp_logging(app_name: str = "inboxai-backend"):
    """
    Set up Google Cloud Logging for the Flask application.

    Args:
        app_name (str): Name of the application for identification in logs

    Returns:
        logging.Logger: Configured logger instance
    """
    try:
        credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not credentials_path:
            raise ValueError(
                "GOOGLE_APPLICATION_CREDENTIALS environment variable not set"
            )

        # Create Cloud Logging client
        client = google.cloud.logging.Client.from_service_account_json(credentials_path)

        # Create handler with application name
        handler = CloudLoggingHandler(client, name=app_name)

        # Create custom formatter for structured logging
        class FlaskStructuredFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "severity": record.levelname,
                    "application": app_name,
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                    "message": record.getMessage(),
                }

                # Add request information if available
                if hasattr(record, "request_id"):
                    log_entry.update(
                        {
                            "request_id": record.request_id,
                            "method": record.method,
                            "path": record.path,
                            "ip": record.ip,
                        }
                    )

                # Add exception info if present
                if record.exc_info:
                    log_entry["exception"] = self.formatException(record.exc_info)

                return json.dumps(log_entry)

        # Apply formatter to handler
        handler.setFormatter(FlaskStructuredFormatter())

        # Get logger and set level
        logger = logging.getLogger(app_name)
        logger.setLevel(logging.INFO)

        # Avoid duplicate handlers
        if not any(isinstance(h, CloudLoggingHandler) for h in logger.handlers):
            logger.addHandler(handler)

        return logger

    except Exception as e:
        # Fallback to standard logging
        fallback_logger = logging.getLogger(app_name)
        fallback_logger.addHandler(logging.StreamHandler())
        fallback_logger.warning(
            f"Failed to setup GCP logging: {str(e)}. Using standard logging."
        )
        return fallback_logger


def log_route(f: Callable) -> Callable:
    """
    Decorator to log API route calls with request details.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        logger = current_app.logger
        request_id = request.headers.get("X-Request-ID", "N/A")

        # Add request info to log record
        logger = logging.LoggerAdapter(
            logger,
            {
                "request_id": request_id,
                "method": request.method,
                "path": request.path,
                "ip": request.remote_addr,
            },
        )

        logger.info(f"API Request - {request.method} {request.path}")

        try:
            result = f(*args, **kwargs)
            logger.info(f"API Response - {request.method} {request.path} - Success")
            return result

        except Exception as e:
            logger.error(
                f"API Error - {request.method} {request.path} - {str(e)}", exc_info=True
            )
            raise

    return decorated
