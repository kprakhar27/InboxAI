import logging
from datetime import datetime
from os.path import dirname, join

import google
from dotenv import load_dotenv
from email_preprocessing.pipelines.email_pipeline import EmailPipeline
from email_preprocessing.pipelines.preprocessing_pipeline import PreprocessingPipeline
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from google.oauth2.credentials import Credentials

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


@cron_bp.route("/reademailsfromgmail", methods=["POST"])
@jwt_required()
def process_emails():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        email = data.get("email")

        if not email:
            logging.warning("Email header is missing")
            return jsonify({"message": "Email header is missing"}), 400

        pipeline = EmailPipeline(email, flow.client_config)
        result = pipeline.process_items()
        email_total = result["emails"]["total"]
        email_saved = result["emails"]["successful"]
        thread_total = result["threads"]["total"]
        thread_saved = result["threads"]["successful"]
        start_date = result["emails"]["timestamps"][0]
        end_date = result["threads"]["timestamps"][1]

        logging.info(
            f"Processed emails for user {user_id}: {email_total} total, {email_saved} saved"
        )
        logging.info(
            f"Processed threads for user {user_id}: {thread_total} total, {thread_saved} saved"
        )

        return (
            jsonify(
                {
                    "status": "success",
                    "data": {
                        "email": email,
                        "emails": {
                            "total": email_total,
                            "saved": email_saved,
                            "failed": email_total - email_saved,
                        },
                        "threads": {
                            "total": thread_total,
                            "saved": thread_saved,
                            "failed": thread_total - thread_saved,
                        },
                        "date_range": {
                            "start": start_date,
                            "end": end_date,
                        },
                    },
                }
            ),
            200,
        )
    except Exception as e:
        logging.error(f"Error processing emails for user {user_id}: {str(e)}")
        return jsonify({"message": f"{user_id}: {str(e)}"}), 500


@cron_bp.route("/preprocessemails", methods=["POST"])
@jwt_required()
def preprocess_emails():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        email = data.get("email")

        if not email:
            logging.warning("Email header is missing")
            return jsonify({"message": "Email header is missing"}), 400

        pipeline = PreprocessingPipeline(email)
        result = pipeline.process_ready_items()
        logging.info(f"Preprocessing result: {result}")

        return jsonify({"status": "success", "data": result}), 200
    except Exception as e:
        logging.error(f"Error preprocessing emails for user {user_id}: {str(e)}")
        return jsonify({"message": f"{user_id}: {str(e)}"}), 500
