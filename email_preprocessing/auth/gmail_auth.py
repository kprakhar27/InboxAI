import logging
from datetime import datetime, timezone

from config.settings import CREDENTIAL_PATH_FOR_GMAIL_API, SCOPES
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from utils.db_handler import DatabaseHandler


class GmailAuthenticator:
    @staticmethod
    def is_token_expired(token):
        if not token or "expiry" not in token:
            return True

        try:
            expiry = datetime.fromisoformat(token["expiry"])
            expiry = (
                expiry.replace(tzinfo=timezone.utc)
                if expiry.tzinfo is None
                else expiry.astimezone(timezone.utc)
            )
            return expiry < datetime.now(timezone.utc)
        except Exception as e:
            logging.error(f"Error checking token expiry: {e}")
            return True

    @staticmethod
    def load_credentials(token):
        if not token:
            return None

        try:
            return Credentials.from_authorized_user_info(token, SCOPES)
        except Exception as e:
            logging.error(f"Error loading credentials: {e}")
            return None

    @staticmethod
    def refresh_credentials(creds):
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                return creds
            except Exception as e:
                logging.error(f"Error refreshing credentials: {e}")
                return None
        return None

    @staticmethod
    def initiate_oauth_flow():
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIAL_PATH_FOR_GMAIL_API, SCOPES
            )
            return flow.run_local_server(port=0)
        except Exception as e:
            logging.error(f"Error during OAuth flow: {e}")
            return None

    @staticmethod
    def get_authenticated_email(creds):
        """
        Fetch the email associated with the authenticated account.
        """
        try:
            service = build("gmail", "v1", credentials=creds)
            profile = service.users().getProfile(userId="me").execute()
            return profile.get("emailAddress")
        except Exception as e:
            logging.error(f"Error fetching authenticated email: {e}")
            return None

    @staticmethod
    def authenticate(email):
        logging.info(f"Authenticating Gmail for: {email}")
        token = DatabaseHandler.fetch_token(email)
        creds = GmailAuthenticator.load_credentials(token) if token else None

        if not creds or not creds.valid or GmailAuthenticator.is_token_expired(token):
            creds = (
                GmailAuthenticator.refresh_credentials(creds)
                if creds
                else GmailAuthenticator.initiate_oauth_flow()
            )

            if creds:
                authenticated_email = GmailAuthenticator.get_authenticated_email(creds)

                # Check if the authenticated email matches the expected email
                if authenticated_email and authenticated_email.lower() == email.lower():
                    DatabaseHandler.save_token(
                        email,
                        {
                            "token": creds.token,
                            "refresh_token": creds.refresh_token,
                            "token_uri": creds.token_uri,
                            "client_id": creds.client_id,
                            "client_secret": creds.client_secret,
                            "scopes": creds.scopes,
                            "universe_domain": creds.universe_domain,
                            "account": creds.account,
                            "expiry": creds.expiry.isoformat(),
                        },
                    )
                else:
                    logging.error(
                        f"Authentication failed: Signed-in email ({authenticated_email}) does not match expected email ({email})"
                    )
                    return None  # Reject mismatched authentication

        return creds
