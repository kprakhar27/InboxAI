import logging
import os

from google_auth_oauthlib.flow import Flow

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_flow():
    """Return a singleton Flow instance."""
    if not hasattr(get_flow, "flow"):
        logger.info("Creating new Flow instance.")
        get_flow.flow = Flow.from_client_secrets_file(
            os.environ["CREDENTIAL_PATH_FOR_GMAIL_API"],
            scopes=[
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/userinfo.email",
            ],
            redirect_uri=os.environ.get("REDIRECT_URI"),
        )
    else:
        logger.info("Using existing Flow instance.")
    return get_flow.flow
