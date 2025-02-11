from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import text

from .models import Users, GoogleToken
from . import db, scheduler

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from datetime import datetime
import os


routes_bp = Blueprint("routes", __name__)


@routes_bp.route("/addprofile", methods=["POST"])
@jwt_required()
def hello():
    return jsonify({"message": "Hello World"}), 200


@routes_bp.route("/getgmaillink", methods=["POST"])
@jwt_required()
def gamail_link():
    data = request.get_json()
    redirect_uri = data.get("redirect_uri", "https://inboxai.tech/redirect")
    if redirect_uri.startswith("http://"):
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    flow = Flow.from_client_secrets_file(
        'credentials.json',
        scopes=['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/userinfo.email'],
        redirect_uri=redirect_uri
    )
    authorization_url, state = flow.authorization_url(prompt='consent')
    return jsonify({"authorization_url": authorization_url, "state": state}), 200

@routes_bp.route("/savegoogletoken", methods=["POST"])
@jwt_required()
def save_google_token():
    data = request.get_json()
    redirect_uri = data.get("redirect_uri", "https://inboxai.tech/redirect")
    if redirect_uri.startswith("http://"):
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    auth_url = data.get("auth_url")
    flow = Flow.from_client_secrets_file(
        'credentials.json',
        scopes=['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/userinfo.email'],
        redirect_uri=redirect_uri
    )
    try:
        flow.fetch_token(authorization_response=auth_url)
        credentials = flow.credentials

        if not credentials or not credentials.token:
            return jsonify({"error": "Failed to fetch token"}), 400

        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        email = user_info.get('email')

        if not email:
            return jsonify({"error": "Failed to fetch email"}), 400

        user_id = get_jwt_identity()
        google_token = GoogleToken(
            user_id=user_id,
            email=email,
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            expires_at=datetime.fromtimestamp(credentials.expiry.timestamp())
        )
        db.session.add(google_token)
        db.session.commit()

        return jsonify({"message": "Successfully added email: " + email}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

def update_all_google_tokens():
    google_tokens = GoogleToken.query.all()
    for google_token in google_tokens:
        try:
            flow = Flow.from_client_secrets_file(
                'credentials.json',
                scopes=['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/userinfo.email']
            )
            flow.credentials = google.oauth2.credentials.Credentials(
                token=None,
                refresh_token=google_token.refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=flow.client_config['client_id'],
                client_secret=flow.client_config['client_secret']
            )
            flow.refresh(flow.credentials)

            google_token.access_token = flow.credentials.token
            google_token.expires_at = datetime.fromtimestamp(flow.credentials.expiry.timestamp())
        except Exception as e:
            print(f"Failed to update token for user {google_token.user_id}: {str(e)}")
    db.session.commit()

scheduler.add_job(update_all_google_tokens, 'interval', hours=1)
