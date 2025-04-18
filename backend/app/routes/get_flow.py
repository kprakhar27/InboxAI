import os

from flask import current_app
from google_auth_oauthlib.flow import Flow

from ..gcp_logger import setup_gcp_logging

# Configure GCP logging
logger = setup_gcp_logging("inboxai-backend-oauth")


def get_flow():
    """
    Return a singleton Flow instance for Google OAuth.

    Returns:
        Flow: Google OAuth flow instance

    Raises:
        ValueError: If required environment variables are missing
    """
    try:
        if not os.environ.get("CREDENTIAL_PATH_FOR_GMAIL_API"):
            logger.error("Missing CREDENTIAL_PATH_FOR_GMAIL_API environment variable")
            raise ValueError("Gmail API credentials path not configured")

        if not os.environ.get("REDIRECT_URI"):
            logger.error("Missing REDIRECT_URI environment variable")
            raise ValueError("OAuth redirect URI not configured")

        if not hasattr(get_flow, "flow"):
            logger.info("Creating new OAuth Flow instance")

            # Create Flow instance
            get_flow.flow = Flow.from_client_secrets_file(
                os.environ["CREDENTIAL_PATH_FOR_GMAIL_API"],
                scopes=[
                    "https://www.googleapis.com/auth/gmail.readonly",
                    "https://www.googleapis.com/auth/userinfo.email",
                ],
                redirect_uri=os.environ.get("REDIRECT_URI"),
            )

            logger.info("Successfully created new OAuth Flow instance")
        else:
            logger.info("Using existing OAuth Flow instance")

        return get_flow.flow

    except Exception as e:
        logger.error(f"Error initializing OAuth flow: {str(e)}", exc_info=True)
        raise
