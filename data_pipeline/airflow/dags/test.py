import json
import logging
import os

import google.cloud.logging
from google.cloud.logging.handlers import CloudLoggingHandler

# Print environment info
print(
    f"GOOGLE_APPLICATION_CREDENTIALS = {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}"
)

# Set up client
client = google.cloud.logging.Client()
print(f"Using project: {client.project}")

# Create a simple handler
handler = CloudLoggingHandler(client)

# Set up logger
logger = logging.getLogger("test_logger")
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# Log a message
logger.info("TEST LOG MESSAGE")

print("Log sent. Check GCP console.")
