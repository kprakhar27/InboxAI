import logging
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from backend.app.models import GoogleToken


class GmailAuthenticator:
    def __init__(self, db_session):
        self.db_session = db_session

    def get_credentials_from_token(self, google_token, client_config):
        """Convert database token to Google credentials."""
        try:
            credentials = Credentials(
                token=google_token.access_token,
                refresh_token=google_token.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_config["client_id"],
                client_secret=client_config["client_secret"],
                scopes=["https://www.googleapis.com/auth/gmail.readonly"],
            )

            # Check if token needs refresh
            if not credentials.valid:
                if credentials.expired and credentials.refresh_token:
                    credentials.refresh(Request())
                    # Update token in database
                    google_token.access_token = credentials.token
                    google_token.expires_at = datetime.fromtimestamp(
                        credentials.expiry.timestamp()
                    )
                    self.db_session.commit()
                else:
                    return None

            return credentials
        except Exception as e:
            logging.error(f"Error creating credentials: {e}")
            return None

    def get_authenticated_email(self, credentials):
        """Verify the email associated with credentials."""
        try:
            service = build("gmail", "v1", credentials=credentials)
            profile = service.users().getProfile(userId="me").execute()
            return profile.get("emailAddress")
        except Exception as e:
            logging.error(f"Error fetching authenticated email: {e}")
            return None

    def authenticate(self, email, client_config):
        """Authenticate using the new token structure."""
        try:
            # Query the new token structure
            google_token = (
                self.db_session.query(GoogleToken).filter_by(email=email).first()
            )
            if not google_token:
                logging.error(f"No token found for email: {email}")
                return None

            credentials = self.get_credentials_from_token(google_token, client_config)
            if not credentials:
                logging.error("Failed to create credentials")
                return None

            # Verify email matches
            authenticated_email = self.get_authenticated_email(credentials)
            if authenticated_email and authenticated_email.lower() == email.lower():
                return credentials
            else:
                logging.error(f"Email mismatch: {authenticated_email} vs {email}")
                return None

        except Exception as e:
            logging.error(f"Authentication error: {e}")
            return None
