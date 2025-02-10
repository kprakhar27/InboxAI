import os

from dotenv import load_dotenv

# Load environment variables
# TODO: Always set the `dotenv_path` path correctly
dotenv_path = "../.env/.env"
load_dotenv(dotenv_path)

# Gmail API configuration
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_TABLE = "gmail_tokens"
CREDENTIAL_PATH_FOR_GMAIL_API = os.getenv("CREDENTIAL_PATH_FOR_GMAIL_API")

# Database configuration
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}

# GCS configuration
BUCKET_NAME = os.getenv("BUCKET_NAME")
EMAIL_FOLDER = os.getenv("EMAIL_FOLDER")
THREAD_FOLDER = os.getenv("THREAD_FOLDER")

# TODO: Ensure the service account key is correctly set in the .env file
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
print(BUCKET_NAME, GOOGLE_APPLICATION_CREDENTIALS)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS
