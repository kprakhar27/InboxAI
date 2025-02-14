import os
import sys
from datetime import datetime
from os.path import dirname, join

import google
from dotenv import load_dotenv
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy import text

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from email_preprocessing.pipelines.email_pipeline import EmailPipeline

from . import db
from .models import GoogleToken, Users

dotenv_path = join(dirname(__file__), ".env")
load_dotenv(dotenv_path)

routes_bp = Blueprint("routes", __name__)

if os.environ.get("REDIRECT_URI").startswith("http://"):
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
else:
    os.environ.pop("OAUTHLIB_INSECURE_TRANSPORT", None)

flow = Flow.from_client_secrets_file(
    "credentials.json",
    scopes=[
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/userinfo.email",
    ],
    redirect_uri=os.environ.get("REDIRECT_URI"),
)


@routes_bp.route("/addprofile", methods=["POST"])
@jwt_required()
def hello():
    return jsonify({"message": "Hello World"}), 200


@routes_bp.route("/getgmaillink", methods=["POST"])
@jwt_required()
def gmail_link():
    authorization_url, state = flow.authorization_url(prompt="consent")
    return jsonify({"authorization_url": authorization_url, "state": state}), 200


@routes_bp.route("/savegoogletoken", methods=["POST"])
@jwt_required()
def save_google_token():
    data = request.get_json()
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    auth_url = data.get("auth_url")
    try:
        flow.fetch_token(authorization_response=auth_url)
        credentials = flow.credentials

        print("credentials", credentials)

        if not credentials or not credentials.token:
            return jsonify({"error": "Failed to fetch token"}), 400

        service = build("oauth2", "v2", credentials=credentials)
        user_info = service.userinfo().get().execute()
        email = user_info.get("email")

        if not email:
            return jsonify({"error": "Failed to fetch email"}), 400

        user_id = get_jwt_identity()
        user = Users.query.filter_by(username=user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        google_token = GoogleToken(
            user_id=user.id,
            email=email,
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            expires_at=datetime.fromtimestamp(credentials.expiry.timestamp()),
        )
        db.session.add(google_token)
        db.session.commit()

        return jsonify({"message": "Successfully added email: " + email}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@routes_bp.route("/updategoogletoken", methods=["POST"])
def update_all_google_tokens():
    # with app.app_context():
    print("Updating Google tokens...", datetime.now())
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
        except Exception as e:
            print(f"Failed to update token for user {google_token.user_id}: {str(e)}")
        db.session.commit()
        return jsonify({"message": "success"}), 200


# Route integration
@routes_bp.route("/processrawemails", methods=["POST"])
@jwt_required()
def process_raw_emails():
    try:
        data = request.get_json()
        email = data.get("email")
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        # Validate inputs
        if not all([email, start_date]):
            return (
                jsonify(
                    {
                        "error": "Missing required parameters",
                        "required": ["email", "start_date"],
                    }
                ),
                400,
            )

        # Initialize pipeline
        pipeline = EmailPipeline(db.session, email, flow.client_config)

        # Store both emails and threads
        email_total, email_saved = pipeline.process_emails(start_date, end_date)
        thread_total, thread_saved = pipeline.process_threads(start_date, end_date)

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
                            "end": end_date or "present",
                        },
                        "timestamp": datetime.now().isoformat(),
                    },
                }
            ),
            200,
        )

    except Exception as e:
        print("Error in process_raw_emails:", e)
        return 200
