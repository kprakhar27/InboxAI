import os
from datetime import datetime
from os.path import dirname, join

from dotenv import load_dotenv
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from googleapiclient.discovery import build
from sqlalchemy import text

from .. import db
from ..models import GoogleToken, Users
from .get_flow import get_flow

dotenv_path = join(dirname(__file__), ".env")
load_dotenv(dotenv_path)

api_bp = Blueprint("routes", __name__)

if os.environ.get("REDIRECT_URI").startswith("http://"):
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
else:
    os.environ.pop("OAUTHLIB_INSECURE_TRANSPORT", None)

flow = get_flow()


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
