import os
from os.path import dirname, join

from dotenv import load_dotenv

dotenv_path = join(dirname(__file__), ".env")
load_dotenv(dotenv_path)

# DB configurations
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT")
DB_NAME = os.environ.get("DB_NAME")

# GCS configurations
BUCKET_NAME = os.getenv("BUCKET_NAME")
EMAIL_FOLDER = os.getenv("EMAIL_FOLDER")
THREAD_FOLDER = os.getenv("THREAD_FOLDER")

# Gmail API configurations
CREDENTIAL_PATH_FOR_GMAIL_API = os.getenv("CREDENTIAL_PATH_FOR_GMAIL_API")

# Google Cloud Storage Service Account Key
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS
# TODO: Make a env variable for this SA key


# create basick congiguration of backend app
class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
