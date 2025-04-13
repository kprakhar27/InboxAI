import json
import os
from datetime import datetime
from os.path import dirname, join
from random import choice, randint
from time import sleep, time

import requests
from dotenv import load_dotenv
from flask import Blueprint, jsonify, redirect, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from googleapiclient.discovery import build
from requests.auth import HTTPBasicAuth
from sqlalchemy import text

from .. import db
from ..models import *
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
        return jsonify({"accounts": [], "total_accounts": 0}), 200

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


@api_bp.route("/ragsources", methods=["GET"])
@jwt_required()
def get_rag_sources():
    """
    Get all available RAG sources.
    Returns a simple list of RAG sources with their IDs and names.
    """
    try:
        # Query all RAG sources
        rag_sources = RAG.query.order_by(RAG.rag_name).all()
        
        sources = [{
            "rag_id": str(source.rag_id),
            "name": source.rag_name
        } for source in rag_sources]
        
        return jsonify({
            "sources": sources,
            "total": len(sources)
        }), 200
        
    except Exception as e:
        return jsonify({
            "error": "Failed to retrieve RAG sources",
            "details": str(e)
        }), 500


@api_bp.route("/createchat", methods=["POST"])
@jwt_required()
def create_chat():
    """
    Create a new chat for the authenticated user.
    
    Request body (optional):
    {
        "name": "Custom Chat Name"
    }
    """
    try:
        # Get user from JWT token
        username = get_jwt_identity()
        user = Users.query.filter_by(username=username).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Get chat name from request or use default
        data = request.get_json() or {}
        chat_name = data.get("name", "New Chat")

        # Create new chat
        new_chat = Chat(
            user_id=user.id,
            name=chat_name
        )
        db.session.add(new_chat)
        db.session.commit()

        # Return chat details
        return jsonify({
            "chat_id": str(new_chat.chat_id),
            "name": new_chat.name,
            "created_at": new_chat.created_at.isoformat()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": "Failed to create chat",
            "details": str(e)
        }), 500
    

@api_bp.route("/getchats", methods=["GET"])
@jwt_required()
def get_chats():
    """
    Get all chats for the authenticated user.
    Returns a list of chats with their IDs, names, and timestamps.
    """
    try:
        # Get user from JWT token
        username = get_jwt_identity()
        user = Users.query.filter_by(username=username).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Query all chats for the user, ordered by creation date (newest first)
        chats = Chat.query.filter_by(user_id=user.id)\
                         .order_by(Chat.created_at.desc())\
                         .all()

        # Format response
        chats_list = [{
            "chat_id": str(chat.chat_id),
            "name": chat.name,
            "created_at": chat.created_at.isoformat()
        } for chat in chats]

        return jsonify({
            "chats": chats_list,
            "total": len(chats_list)
        }), 200

    except Exception as e:
        return jsonify({
            "error": "Failed to retrieve chats",
            "details": str(e)
        }), 400
    

@api_bp.route("/getmessages/<chat_id>", methods=["GET"])
@jwt_required()
def get_messages(chat_id):
    """
    Get all messages for a specific chat.
    
    Args:
        chat_id: UUID of the chat to retrieve messages from
        
    Returns:
        List of messages with their metadata
    """
    try:
        # Get user from JWT token
        username = get_jwt_identity()
        user = Users.query.filter_by(username=username).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Verify chat exists and belongs to user
        chat = Chat.query.filter_by(
            chat_id=chat_id,
            user_id=user.id
        ).first()
        if not chat:
            return jsonify({"error": "Chat not found or access denied"}), 404

        # Query messages for this chat
        messages = Message.query\
            .filter_by(chat_id=chat_id)\
            .order_by(Message.created_at.asc())\
            .all()

        # Format response
        messages_list = [{
            "message_id": str(msg.message_id),
            "query_hash": msg.query_hash,
            "response_hash": msg.response_hash,
            "rag_id": str(msg.rag_id),
            "response_time_ms": msg.response_time_ms,
            "feedback": msg.feedback,
            "created_at": msg.created_at.isoformat()
        } for msg in messages]

        return jsonify({
            "chat_id": chat_id,
            "messages": messages_list,
            "total": len(messages_list)
        }), 200

    except ValueError:
        return jsonify({
            "error": "Invalid chat ID format"
        }), 400
    except Exception as e:
        return jsonify({
            "error": "Failed to retrieve messages",
            "details": str(e)
        }), 400
    
@api_bp.route("/inferencefeedback", methods=["POST"])
@jwt_required()
def record_inference_feedback():
    """
    Record user feedback on a chat message response.
    
    Request body:
    {
        "message_id": "uuid-string",
        "feedback": boolean
    }
    """
    try:
        # Get user from JWT token
        username = get_jwt_identity()
        user = Users.query.filter_by(username=username).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Validate request data
        data = request.get_json()
        if not data or "message_id" not in data or "feedback" not in data:
            return jsonify({
                "error": "Missing required fields",
                "details": "message_id and feedback are required"
            }), 400

        message_id = data["message_id"]
        feedback = bool(data["feedback"])

        # Get message and verify ownership
        message = Message.query.filter_by(
            message_id=message_id,
            user_id=user.id
        ).first()
        
        if not message:
            return jsonify({
                "error": "Message not found or access denied"
            }), 404

        # Update feedback
        message.feedback = feedback
        db.session.commit()

        return jsonify({
            "message": "Feedback recorded successfully",
            "message_id": str(message_id),
            "feedback": feedback
        }), 200

    except ValueError as ve:
        return jsonify({
            "error": "Invalid input format",
            "details": str(ve)
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": "Failed to record feedback",
            "details": str(e)
        }), 400


@api_bp.route("/getinference", methods=["POST"])
@jwt_required()
def get_inference():
    """
    Process a query and return a dummy chatbot response.
    
    Request body:
    {
        "query": "text of the question",
        "chat_id": "uuid-string",
        "rag_id": "uuid-string"
    }
    """
    try:
        # Get user from JWT token
        username = get_jwt_identity()
        user = Users.query.filter_by(username=username).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Validate request data
        data = request.get_json()
        if not data or not all(k in data for k in ["query", "chat_id", "rag_id"]):
            return jsonify({
                "error": "Missing required fields",
                "details": "query, chat_id, and rag_id are required"
            }), 400

        # Verify chat exists and belongs to user
        chat = Chat.query.filter_by(
            chat_id=data["chat_id"],
            user_id=user.id
        ).first()
        if not chat:
            return jsonify({"error": "Chat not found or access denied"}), 404

        # Verify RAG source exists
        rag_source = RAG.query.filter_by(rag_id=data["rag_id"]).first()
        if not rag_source:
            return jsonify({"error": "RAG source not found"}), 404

        # Start timing
        start_time = time()
        
        # Generate dummy response
        dummy_responses = [
            "Based on your email history, the last meeting was about project updates.",
            "I found an email about that topic from last week. It mentioned deadlines.",
            "According to recent emails, this was discussed in yesterday's team sync.",
            "Your email thread from March 15th covered these points in detail.",
            "I see several emails about this topic in your inbox from different team members."
        ]
        sleep(randint(1, 5))
        response = choice(dummy_responses)
        
        # Calculate response time
        response_time_ms = int((time() - start_time) * 1000)

        # Create new message record
        message = Message(
            chat_id=data["chat_id"],
            user_id=user.id,
            rag_id=data["rag_id"],
            response_time_ms=response_time_ms
        )
        
        # Set query and response hashes
        message.set_query(data["query"])
        message.set_response(response)

        # Save to database
        db.session.add(message)
        db.session.commit()

        # Return response
        return jsonify({
            "message_id": str(message.message_id),
            "response": response,
            "rag_id": str(message.rag_id),
            "query_hash": message.query_hash,
            "response_hash": message.response_hash,
            "response_time_ms": message.response_time_ms
        }), 200

    except ValueError as ve:
        return jsonify({
            "error": "Invalid input format",
            "details": str(ve)
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": "Failed to process inference request",
            "details": str(e)
        }), 400