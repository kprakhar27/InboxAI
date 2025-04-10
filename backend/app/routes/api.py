import json
import os
from datetime import datetime
from os.path import dirname, join

import requests
from dotenv import load_dotenv
from flask import Blueprint, jsonify, redirect, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from googleapiclient.discovery import build
from requests.auth import HTTPBasicAuth
from sqlalchemy import text

from .. import db
from ..models import (
    EmailPreprocessingSummary,
    EmailReadTracker,
    EmailRunStatus,
    GoogleToken,
    Users,
)
from .get_flow import get_flow

dotenv_path = join(dirname(__file__), ".env")
load_dotenv(dotenv_path)

api_bp = Blueprint("routes", __name__)

if os.environ.get("REDIRECT_URI").startswith("http://"):
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
else:
    os.environ.pop("OAUTHLIB_INSECURE_TRANSPORT", None)

flow = get_flow()


@api_bp.route("/redirect", methods=["GET", "POST"])
def redirect_url():
    params = request.args.to_dict()
    params["api_url"] = request.base_url
    url = "https://inboxai.tech/#/redirect?" + "&".join(
        [f"{k}={v}" for k, v in params.items()]
    )
    print({"params": params, "url": url})
    return redirect(url, code=301)


@api_bp.route("/addprofile", methods=["POST"])
@jwt_required()
def hello():
    return jsonify({"message": "Hello World"}), 200


@api_bp.route("/getgmaillink", methods=["POST"])
@jwt_required()
def gmail_link():
    authorization_url, state = flow.authorization_url(prompt="consent")
    return jsonify({"authorization_url": authorization_url, "state": state}), 200


@api_bp.route("/savegoogletoken", methods=["POST"])
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

        # Check if token already exists for this user and email
        existing_token = GoogleToken.query.filter_by(
            user_id=user.id, email=email
        ).first()

        if existing_token:
            # Update existing token
            existing_token.access_token = credentials.token
            existing_token.refresh_token = credentials.refresh_token
            existing_token.expires_at = datetime.fromtimestamp(
                credentials.expiry.timestamp()
            )
        else:
            # Create new token
            google_token = GoogleToken(
                user_id=user.id,
                email=email,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                expires_at=datetime.fromtimestamp(credentials.expiry.timestamp()),
            )
            db.session.add(google_token)

        db.session.commit()
        return jsonify({"message": "Successfully added/updated email: " + email}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@api_bp.route("/getconnectedaccounts", methods=["GET"])
@jwt_required()
def get_connected_accounts():
    user_id = get_jwt_identity()
    user = Users.query.filter_by(username=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Get all Google tokens for the user
    google_tokens = GoogleToken.query.filter_by(user_id=user.id).all()
    if not google_tokens:
        return jsonify({"error": "No connected accounts found"}), 404

    # Process each account
    accounts = {}
    for token in google_tokens:
        email = token.email
        if email not in accounts:
            # Get run status
            run_status = EmailRunStatus.query.filter_by(
                user_id=user.id, email=email
            ).first()

            # Get last read time
            last_read = (
                EmailReadTracker.query.filter_by(user_id=user.id, email=email)
                .order_by(EmailReadTracker.last_read_at.desc())
                .first()
            )

            # Get email preprocessing summary
            summary = (
                db.session.query(
                    db.func.sum(EmailPreprocessingSummary.total_emails_processed).label(
                        "total_emails"
                    )
                )
                .filter_by(user_id=user.id, email=email)
                .first()
            )

            accounts[email] = {
                "email": email,
                "expires_at": token.expires_at,
                "run_status": run_status.run_status if run_status else "NO STATUS",
                "last_read": last_read.last_read_at if last_read else "NO LAST READ",
                "total_emails_processed": (
                    summary.total_emails if summary and summary.total_emails else 0
                ),
            }

    # Convert dict to sorted list
    account_list = sorted(accounts.values(), key=lambda x: x["email"])

    return jsonify({"accounts": account_list, "total_accounts": len(account_list)}), 200


@api_bp.route("/refreshemails", methods=["POST"])
@jwt_required()
def refresh_emails():
    user_id = get_jwt_identity()
    user = Users.query.filter_by(username=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    google_tokens = GoogleToken.query.filter_by(user_id=user.id).all()
    if not google_tokens:
        return jsonify({"error": "No connected accounts found"}), 404

    airflow_ip = os.environ.get("AIRFLOW_API_IP")
    airflow_user = os.environ.get("AIRFLOW_API_USER")
    airflow_pass = os.environ.get("AIRFLOW_API_PASSWORD")
    airflow_port = os.environ.get("AIRFLOW_API_PORT")

    airflow_url = f"http://{airflow_ip}:{airflow_port}/api/v1/dags/email_create_batch_pipeline/dagRuns"
    airflow_auth = HTTPBasicAuth(airflow_user, airflow_pass)
    headers = {"Content-Type": "application/json"}

    successful_triggers = []
    failed_triggers = []

    for token in google_tokens:
        user_id = token.user_id
        email = token.email

        payload = {"conf": {"email_address": email, "user_id": str(user_id)}}

        try:
            # Trigger the DAG
            response = requests.post(
                airflow_url,
                auth=airflow_auth,
                headers=headers,
                data=json.dumps(payload),
                timeout=10,
            )

            if response.status_code == 200:
                successful_triggers.append(email)
            else:
                failed_triggers.append(
                    {
                        "email": email,
                        "status_code": response.status_code,
                        "response": response.text,
                    }
                )

        except requests.exceptions.RequestException as e:
            failed_triggers.append({"email": email, "error": str(e)})

    return jsonify(
        {
            "message": f"Triggered email refresh for {len(successful_triggers)} accounts",
            "successful": successful_triggers,
            "failed": failed_triggers,
        }
    )


@api_bp.route("/removeemail", methods=["POST"])
@jwt_required()
def remove_email():
    data = request.get_json()
    email = data.get("email")
    username = get_jwt_identity()

    # Get the user from database to get the actual user ID
    user = Users.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    user_id = user.id  # This will be the actual UUID

    airflow_ip = os.environ.get("AIRFLOW_API_IP")
    airflow_user = os.environ.get("AIRFLOW_API_USER")
    airflow_pass = os.environ.get("AIRFLOW_API_PASSWORD")
    airflow_port = os.environ.get("AIRFLOW_API_PORT")

    airflow_url = (
        f"http://{airflow_ip}:{airflow_port}/api/v1/dags/data_deletion_pipeline/dagRuns"
    )
    airflow_auth = HTTPBasicAuth(airflow_user, airflow_pass)
    headers = {"Content-Type": "application/json"}
    payload = {"conf": {"email_address": email, "user_id": str(user_id)}}

    try:
        # Trigger the DAG
        response = requests.post(
            airflow_url,
            auth=airflow_auth,
            headers=headers,
            data=json.dumps(payload),
            timeout=10,
        )

        if response.status_code == 200:
            return (
                jsonify(
                    {
                        "message": f"Successfully triggered email removal pipeline, user: {user_id}, email: {email}",
                    }
                ),
                200,
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    return (
        jsonify({"error": f"Failed to trigger email removal pipeline, {str(e)}"}),
        400,
    )
