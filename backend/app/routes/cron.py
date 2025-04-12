import logging
import os
from datetime import datetime
from os.path import dirname, join

import google
import requests
from dotenv import load_dotenv
from flask import Blueprint, jsonify, request
from google.oauth2.credentials import Credentials
from requests.auth import HTTPBasicAuth

from .. import db
from ..models import GoogleToken, Users
from .get_flow import get_flow

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

dotenv_path = join(dirname(__file__), ".env")
load_dotenv(dotenv_path)

cron_bp = Blueprint("cron", __name__)
flow = get_flow()


@cron_bp.route("/updategoogletoken", methods=["POST"])
def update_all_google_tokens():
    logging.info("Updating Google tokens...")
    google_tokens = GoogleToken.query.all()
    for google_token in google_tokens:
        try:
            credentials = Credentials(
                token=None,
                refresh_token=google_token.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=flow.client_config["client_id"],
                client_secret=flow.client_config["client_secret"],
            )
            credentials.refresh(google.auth.transport.requests.Request())

            google_token.access_token = credentials.token
            google_token.expires_at = datetime.fromtimestamp(
                credentials.expiry.timestamp()
            )
            logging.info(f"Successfully updated token for user {google_token.user_id}")
        except Exception as e:
            logging.error(
                f"Failed to update token for user {google_token.user_id}: {str(e)}"
            )
            db.session.commit()
    return jsonify({"message": "success"}), 200
