# api.py
import importlib
import json
import os
import sys
from datetime import datetime
from os.path import dirname, join
from random import choice, randint, random
from time import sleep, time

import openai
import requests
from dotenv import load_dotenv
from flask import Blueprint, current_app, jsonify, redirect, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from googleapiclient.discovery import build
from requests.auth import HTTPBasicAuth
from sqlalchemy import text

from .. import db
from ..gcp_logger import log_route
from ..models import *
from ..rag.RAGConfig import RAGConfig
from .get_flow import get_flow

dotenv_path = join(dirname(__file__), ".env")
load_dotenv(dotenv_path)

api_bp = Blueprint("routes", __name__)
logger = current_app.logger

if os.environ.get("REDIRECT_URI").startswith("http://"):
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
else:
    os.environ.pop("OAUTHLIB_INSECURE_TRANSPORT", None)

flow = get_flow()

def get_class_from_input(module_path: str, class_name: str):
    """
    Dynamically load a class from a given file path.
    
    Args:
        module_path: str – full path to the .py file
        class_name: str – class name defined in that module

    Returns:
        class object
    """
    logger.debug(f"Attempting to load class '{class_name}' from {module_path}")
    module_name = os.path.splitext(os.path.basename(module_path))[0]  # e.g., RAGConfig
    logger.debug(f"Module name: {module_name}")
    spec = importlib.util.spec_from_file_location(module_name, module_path)

    if spec is None or spec.loader is None:
        logger.error(f"Error: Could not load spec for {module_path}")
        raise ImportError(f"Could not load spec for {module_path}")

    logger.debug(f"Successfully loaded spec for {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    logger.debug(f"Executing module {module_name}")
    spec.loader.exec_module(module)

    if not hasattr(module, class_name):
        logger.error(f"Error: Class '{class_name}' not found in {module_path}")
        raise ImportError(f"Class '{class_name}' not found in {module_path}")

    logger.debug(f"Successfully loaded class '{class_name}' from {module_path}")
    return getattr(module, class_name)


@api_bp.route("/redirect", methods=["GET", "POST"])
@log_route
def redirect_url():
    params = request.args.to_dict()
    params["api_url"] = request.base_url
    url = "https://inboxai.tech/#/redirect?" + "&".join(
        [f"{k}={v}" for k, v in params.items()]
    )
    logger.info(f"Redirecting with parameters: {params}")
    return redirect(url, code=301)


@api_bp.route("/addprofile", methods=["POST"])
@jwt_required()
@log_route
def hello():
    user_id = get_jwt_identity()
    logger.info(f"Hello World endpoint accessed by user: {user_id}")
    return jsonify({"message": "Hello World"}), 200


@api_bp.route("/getgmaillink", methods=["POST"])
@jwt_required()
@log_route
def gmail_link():
    user_id = get_jwt_identity()
    logger.info(f"Gmail authorization link requested by user: {user_id}")
    authorization_url, state = flow.authorization_url(prompt="consent")
    logger.debug(f"Generated state: {state}")
    return jsonify({"authorization_url": authorization_url, "state": state}), 200


@api_bp.route("/savegoogletoken", methods=["POST"])
@jwt_required()
@log_route
def save_google_token():
    user_id = get_jwt_identity()
    logger.info(f"Token save request received from user: {user_id}")
    
    data = request.get_json()
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    auth_url = data.get("auth_url")
    
    try:
        logger.debug(f"Fetching token with auth_url: {auth_url}")
        flow.fetch_token(authorization_response=auth_url)
        credentials = flow.credentials

        if not credentials or not credentials.token:
            logger.error("Failed to fetch token")
            return jsonify({"error": "Failed to fetch token"}), 400

        logger.debug("Building OAuth2 service")
        service = build("oauth2", "v2", credentials=credentials)
        user_info = service.userinfo().get().execute()
        email = user_info.get("email")

        if not email:
            logger.error("Failed to fetch email from user info")
            return jsonify({"error": "Failed to fetch email"}), 400

        logger.info(f"Retrieved email: {email} for user: {user_id}")
        
        user = Users.query.filter_by(username=user_id).first()
        if not user:
            logger.error(f"User not found: {user_id}")
            return jsonify({"error": "User not found"}), 404

        # Check if token already exists for this user and email
        existing_token = GoogleToken.query.filter_by(
            user_id=user.id, email=email
        ).first()

        if existing_token:
            # Update existing token
            logger.info(f"Updating existing token for email: {email}")
            existing_token.access_token = credentials.token
            existing_token.refresh_token = credentials.refresh_token
            existing_token.expires_at = datetime.fromtimestamp(
                credentials.expiry.timestamp()
            )
        else:
            # Create new token
            logger.info(f"Creating new token for email: {email}")
            google_token = GoogleToken(
                user_id=user.id,
                email=email,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                expires_at=datetime.fromtimestamp(credentials.expiry.timestamp()),
            )
            db.session.add(google_token)

        db.session.commit()
        logger.info(f"Successfully saved/updated token for email: {email}")
        return jsonify({"message": "Successfully added/updated email: " + email}), 200
    except Exception as e:
        logger.error(f"Error saving Google token: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@api_bp.route("/getconnectedaccounts", methods=["GET"])
@jwt_required()
@log_route
def get_connected_accounts():
    user_id = get_jwt_identity()
    logger.info(f"Connected accounts requested by user: {user_id}")
    
    user = Users.query.filter_by(username=user_id).first()
    if not user:
        logger.error(f"User not found: {user_id}")
        return jsonify({"error": "User not found"}), 404

    # Get all Google tokens for the user
    google_tokens = GoogleToken.query.filter_by(user_id=user.id).all()
    if not google_tokens:
        logger.info(f"No connected accounts found for user: {user_id}")
        return jsonify({"accounts": [], "total_accounts": 0}), 200

    # Process each account
    accounts = {}
    for token in google_tokens:
        email = token.email
        if email not in accounts:
            logger.debug(f"Processing account: {email}")
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
    logger.info(f"Retrieved {len(account_list)} connected accounts for user: {user_id}")

    return jsonify({"accounts": account_list, "total_accounts": len(account_list)}), 200


@api_bp.route("/refreshemails", methods=["POST"])
@jwt_required()
@log_route
def refresh_emails():
    user_id = get_jwt_identity()
    logger.info(f"Email refresh requested by user: {user_id}")
    
    user = Users.query.filter_by(username=user_id).first()
    if not user:
        logger.error(f"User not found: {user_id}")
        return jsonify({"error": "User not found"}), 404

    google_tokens = GoogleToken.query.filter_by(user_id=user.id).all()
    if not google_tokens:
        logger.error(f"No connected accounts found for user: {user_id}")
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

    logger.debug(f"Airflow URL: {airflow_url}")

    for token in google_tokens:
        user_id = token.user_id
        email = token.email
        logger.info(f"Triggering refresh for email: {email}")

        payload = {"conf": {"email_address": email, "user_id": str(user_id)}}

        try:
            # Trigger the DAG
            logger.debug(f"Sending request to Airflow for email: {email}")
            response = requests.post(
                airflow_url,
                auth=airflow_auth,
                headers=headers,
                data=json.dumps(payload),
                timeout=10,
            )

            if response.status_code == 200:
                logger.info(f"Successfully triggered refresh for email: {email}")
                successful_triggers.append(email)
            else:
                logger.error(f"Failed to trigger refresh for email: {email}, status: {response.status_code}, response: {response.text}")
                failed_triggers.append(
                    {
                        "email": email,
                        "status_code": response.status_code,
                        "response": response.text,
                    }
                )

        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception when triggering refresh for email: {email}, error: {str(e)}")
            failed_triggers.append({"email": email, "error": str(e)})

    logger.info(f"Email refresh complete - successful: {len(successful_triggers)}, failed: {len(failed_triggers)}")
    return jsonify(
        {
            "message": f"Triggered email refresh for {len(successful_triggers)} accounts",
            "successful": successful_triggers,
            "failed": failed_triggers,
        }
    )


@api_bp.route("/removeemail", methods=["POST"])
@jwt_required()
@log_route
def remove_email():
    username = get_jwt_identity()
    logger.info(f"Email removal requested by user: {username}")
    
    data = request.get_json()
    email = data.get("email")
    
    if not email:
        logger.error("No email provided for removal")
        return jsonify({"error": "Email is required"}), 400
    
    logger.info(f"Attempting to remove email: {email}")

    # Get the user from database to get the actual user ID
    user = Users.query.filter_by(username=username).first()
    if not user:
        logger.error(f"User not found: {username}")
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
        logger.debug(f"Sending request to Airflow for email removal: {email}")
        response = requests.post(
            airflow_url,
            auth=airflow_auth,
            headers=headers,
            data=json.dumps(payload),
            timeout=10,
        )

        if response.status_code == 200:
            logger.info(f"Successfully triggered email removal for: {email}")
            return (
                jsonify(
                    {
                        "message": f"Successfully triggered email removal pipeline, user: {user_id}, email: {email}",
                    }
                ),
                200,
            )
        else:
            logger.error(f"Failed to trigger email removal, status: {response.status_code}, response: {response.text}")
            
    except Exception as e:
        logger.error(f"Error removing email: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400
        
    return (
        jsonify({"error": f"Failed to trigger email removal pipeline, {str(e)}"}),
        400,
    )


@api_bp.route("/ragsources", methods=["GET"])
@jwt_required()
@log_route
def get_rag_sources():
    """
    Get all available RAG sources.
    Returns a simple list of RAG sources with their IDs and names.
    """
    user_id = get_jwt_identity()
    logger.info(f"RAG sources requested by user: {user_id}")
    
    try:
        # Query all RAG sources
        rag_sources = RAG.query.filter_by(is_available=True).order_by(RAG.rag_name).all()

        sources = [
            {"rag_id": str(source.rag_id), "name": source.rag_name}
            for source in rag_sources
        ]

        logger.info(f"Retrieved {len(sources)} RAG sources")
        return jsonify({"sources": sources, "total": len(sources)}), 200

    except Exception as e:
        logger.error(f"Error retrieving RAG sources: {str(e)}", exc_info=True)
        return (
            jsonify({"error": "Failed to retrieve RAG sources", "details": str(e)}),
            500,
        )


@api_bp.route("/createchat", methods=["POST"])
@jwt_required()
@log_route
def create_chat():
    """
    Create a new chat for the authenticated user.

    Request body (optional):
    {
        "name": "Custom Chat Name"
    }
    """
    username = get_jwt_identity()
    logger.info(f"Chat creation requested by user: {username}")
    
    try:
        # Get user from JWT token
        user = Users.query.filter_by(username=username).first()
        if not user:
            logger.error(f"User not found: {username}")
            return jsonify({"error": "User not found"}), 404

        # Get chat name from request or use default
        data = request.get_json() or {}
        chat_name = data.get("name", "New Chat")
        logger.debug(f"Creating chat with name: {chat_name}")

        # Create new chat
        new_chat = Chat(user_id=user.id, name=chat_name)
        db.session.add(new_chat)
        db.session.commit()

        # Return chat details
        logger.info(f"Successfully created chat: {str(new_chat.chat_id)}")
        return (
            jsonify(
                {
                    "chat_id": str(new_chat.chat_id),
                    "name": new_chat.name,
                    "created_at": new_chat.created_at.isoformat(),
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating chat: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to create chat", "details": str(e)}), 500


@api_bp.route("/getchats", methods=["GET"])
@jwt_required()
@log_route
def get_chats():
    """
    Get all chats for the authenticated user.
    Returns a list of chats with their IDs, names, and timestamps.
    """
    username = get_jwt_identity()
    logger.info(f"Chats requested by user: {username}")
    
    try:
        # Get user from JWT token
        user = Users.query.filter_by(username=username).first()
        if not user:
            logger.error(f"User not found: {username}")
            return jsonify({"error": "User not found"}), 404

        # Query all chats for the user, ordered by creation date (newest first)
        chats = (
            Chat.query.filter_by(user_id=user.id).order_by(Chat.created_at.desc()).all()
        )

        # Format response
        chats_list = [
            {
                "chat_id": str(chat.chat_id),
                "name": chat.name,
                "created_at": chat.created_at.isoformat(),
            }
            for chat in chats
        ]

        logger.info(f"Retrieved {len(chats_list)} chats for user: {username}")
        return jsonify({"chats": chats_list, "total": len(chats_list)}), 200

    except Exception as e:
        logger.error(f"Error retrieving chats: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to retrieve chats", "details": str(e)}), 400


@api_bp.route("/getmessages/<chat_id>", methods=["GET"])
@jwt_required()
@log_route
def get_messages(chat_id):
    """
    Get all messages for a specific chat.
    """
    username = get_jwt_identity()
    logger.info(f"Messages requested for chat: {chat_id} by user: {username}")
    
    try:
        # Get user from JWT token
        user = Users.query.filter_by(username=username).first()
        if not user:
            logger.error(f"User not found: {username}")
            return jsonify({"error": "User not found"}), 404

        # Verify chat exists and belongs to user
        chat = Chat.query.filter_by(chat_id=chat_id, user_id=user.id).first()
        if not chat:
            logger.error(f"Chat not found or access denied: {chat_id}")
            return jsonify({"error": "Chat not found or access denied"}), 404

        # Query messages for this chat
        messages = (
            db.session.query(Message)
            .filter(Message.chat_id == chat_id)
            .order_by(Message.created_at.asc())
            .all()
        )

        # Format response - show original response only if not toxic
        messages_list = [
            {
                "message_id": str(msg.message_id),
                "query": msg.query,
                "response": (
                    "I apologize, but I cannot provide this response as it may contain inappropriate content."
                    if msg.is_toxic
                    else msg.response
                ),
                "rag_id": str(msg.rag_id),
                "response_time_ms": msg.response_time_ms,
                "feedback": msg.feedback,
                "is_toxic": msg.is_toxic,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in messages
        ]

        logger.info(f"Retrieved {len(messages_list)} messages for chat: {chat_id}")
        return (
            jsonify(
                {
                    "chat_id": chat_id,
                    "messages": messages_list,
                    "total": len(messages_list),
                }
            ),
            200,
        )

    except ValueError:
        logger.error(f"Invalid chat ID format: {chat_id}")
        return jsonify({"error": "Invalid chat ID format"}), 400
    except Exception as e:
        logger.error(f"Error retrieving messages: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to retrieve messages", "details": str(e)}), 400


@api_bp.route("/inferencefeedback", methods=["POST"])
@jwt_required()
@log_route
def record_inference_feedback():
    """
    Record user feedback on a chat message response.

    Request body:
    {
        "message_id": "uuid-string",
        "feedback": boolean
    }
    """
    username = get_jwt_identity()
    logger.info(f"Inference feedback received from user: {username}")
    
    try:
        # Get user from JWT token
        user = Users.query.filter_by(username=username).first()
        if not user:
            logger.error(f"User not found: {username}")
            return jsonify({"error": "User not found"}), 404

        # Validate request data
        data = request.get_json()
        if not data or "message_id" not in data or "feedback" not in data:
            logger.error("Missing required fields in feedback request")
            return (
                jsonify(
                    {
                        "error": "Missing required fields",
                        "details": "message_id and feedback are required",
                    }
                ),
                400,
            )

        message_id = data["message_id"]
        feedback = bool(data["feedback"])
        logger.debug(f"Recording feedback: {feedback} for message: {message_id}")

        # Get message and verify ownership
        message = db.session.query(Message).filter_by(
            message_id=message_id, user_id=user.id
        ).first()

        if not message:
            logger.error(f"Message not found or access denied: {message_id}")
            return jsonify({"error": "Message not found or access denied"}), 404

        # Update feedback
        message.feedback = feedback
        db.session.commit()
        logger.info(f"Feedback recorded successfully for message: {message_id}")

        return (
            jsonify(
                {
                    "message": "Feedback recorded successfully",
                    "message_id": str(message_id),
                    "feedback": feedback,
                }
            ),
            200,
        )

    except ValueError as ve:
        logger.error(f"Invalid input format: {str(ve)}")
        return jsonify({"error": "Invalid input format", "details": str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to record feedback: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to record feedback", "details": str(e)}), 400


@api_bp.route("/getinference", methods=["POST"])
@jwt_required()
@log_route
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
        username = get_jwt_identity()
        logger.info(f"Inference request received from user: {username}")
        
        # Get user from JWT token
        user = Users.query.filter_by(username=username).first()
        if not user:
            logger.error(f"User not found: {username}")
            return jsonify({"error": "User not found"}), 404

        # Validate request data
        data = request.get_json()
        logger.debug(f"Request data: {data}")
        if not data or not all(k in data for k in ["query", "chat_id", "rag_id"]):
            logger.error("Missing required fields in inference request")
            return (
                jsonify(
                    {
                        "error": "Missing required fields",
                        "details": "query, chat_id, and rag_id are required",
                    }
                ),
                400,
            )

        # Verify chat exists and belongs to user
        chat = Chat.query.filter_by(chat_id=data["chat_id"], user_id=user.id).first()
        if not chat:
            logger.error(f"Chat not found or access denied for chat_id: {data['chat_id']}")
            return jsonify({"error": "Chat not found or access denied"}), 404

        # Verify RAG source exists
        rag_source = RAG.query.filter_by(rag_id=data["rag_id"]).first()
        if not rag_source:
            logger.error(f"RAG source not found for rag_id: {data['rag_id']}")
            return jsonify({"error": "RAG source not found"}), 404

        # Start timing
        start_time = time()
        logger.debug("Started timing for inference")

        messages = (
            db.session.query(Message)
            .filter_by(chat_id=data["chat_id"], user_id=user.id)
            .order_by(Message.created_at.desc())
            .limit(3)
            .all()
        )
        logger.debug(f"Retrieved {len(messages)} recent messages")

        # Create a single string of conversation if messages exist
        conversation_history = (
            "\n".join(
                [
                    f"User: {msg.query}\nBot: {msg.response}"
                    for msg in reversed(messages)
                ]
            )
            if messages
            else ""
        )
        logger.debug(f"Conversation history prepared, length: {len(conversation_history)}")

        # Get context
        context = messages[0].context if messages else ""
        logger.debug(f"Context prepared, length: {len(context) if context else 0}")

        # RAG Inference
        logger.info("Initializing RAG configuration")
        config = RAGConfig(
            embedding_model=os.getenv("EMBEDDING_MODEL"),
            llm_model=os.getenv("LLM_MODEL"),
            top_k=int(os.getenv("TOP_K")),
            temperature=float(os.getenv("TEMPERATURE")),
            collection_name=str(user.id),
            host=os.getenv("CHROMA_HOST"),
            port=os.getenv("CHROMA_PORT"),
            llm_api_key=os.getenv("GROQ_API_KEY"),
            embedding_api_key=os.getenv("OPENAI_API_KEY"),
        )

        rag_config_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__), "..", "rag", rag_source.rag_name + ".py"
            )
        )
        logger.debug(f"RAG config path: {rag_config_path}")

        logger.info(f"Loading RAG pipeline class: {rag_source.rag_name}")
        Pipeline = get_class_from_input(rag_config_path, rag_source.rag_name)
        
        if Pipeline:
            # Initialize RAG pipeline
            logger.debug("Initializing RAG pipeline")
            rag_pipeline = Pipeline(config)
        else:
            logger.error(f"Invalid RAG source: {rag_source.rag_name}")
            return jsonify({"error": "Invalid RAG source"}), 400
        
        logger.info(f"Executing query with RAG pipeline: {data['query'][:50]}...")
        response = rag_pipeline.query(data["query"], context, conversation_history)
        logger.debug("RAG pipeline response received")

        # Use OpenAI API to check toxicity
        logger.info("Checking response for toxicity")
        openai.api_key = os.getenv("OPENAI_API_KEY")
        moderation_response = openai.moderations.create(
            model="omni-moderation-latest", input=response["response"]
        )
        
        is_toxic = moderation_response.results[0].flagged
        logger.info(f"Toxicity check result: {'toxic' if is_toxic else 'not toxic'}")

        # If toxic, store original response but send safe message
        displayed_response = (
            "I apologize, but I cannot provide this response as it may contain inappropriate content."
            if is_toxic
            else response["response"]
        )

        # Calculate response time
        response_time_ms = int((time() - start_time) * 1000)
        logger.info(f"Response time: {response_time_ms}ms")

        # Create new message record
        logger.debug("Creating message record")
        message = Message(
            chat_id=data["chat_id"],
            user_id=user.id,
            rag_id=data["rag_id"],
            query=data["query"],
            response=response["response"],  # Store original response
            context=response["retrieved_documents"],
            response_time_ms=response_time_ms,
            is_toxic=is_toxic,
            toxicity_response=moderation_response.model_dump(),  # Convert to dict
        )

        # Save to database
        db.session.add(message)
        db.session.commit()
        logger.info(f"Message saved to database with ID: {message.message_id}")

        # Return response (with safe message if toxic)
        return (
            jsonify(
                {
                    "message_id": str(message.message_id),
                    "response": displayed_response,
                    "rag_id": str(message.rag_id),
                    "query": message.query,
                    "response_time_ms": message.response_time_ms,
                    "is_toxic": message.is_toxic,
                }
            ),
            200,
        )

    except ValueError as ve:
        logger.error(f"ValueError in inference: {str(ve)}")
        return jsonify({"error": "Invalid input format", "details": str(ve)}), 400
    except Exception as e:
        logger.error(f"Exception in inference: {str(e)}", exc_info=True)
        import traceback
        logger.error(traceback.format_exc())
        db.session.rollback()
        return (
            jsonify(
                {"error": "Failed to process inference request", "details": str(e)}
            ),
            400,
        )

@api_bp.route("/deletechats", methods=["POST"])
@jwt_required()
@log_route
def delete_chats():
    """
    Delete all chats for the authenticated user.
    """
    username = get_jwt_identity()
    logger.info(f"Chat deletion requested by user: {username}")
    
    try:
        # Get user from JWT token
        user = Users.query.filter_by(username=username).first()
        if not user:
            logger.error(f"User not found: {username}")
            return jsonify({"error": "User not found"}), 404

        # Delete all messages first due to foreign key constraints
        Message.query.filter_by(user_id=user.id).delete()
        
        # Delete all chats for the user
        deleted_count = Chat.query.filter_by(user_id=user.id).delete()
        
        db.session.commit()
        logger.info(f"Successfully deleted {deleted_count} chats for user: {username}")
        
        return jsonify({
            "message": f"Successfully deleted {deleted_count} chats",
            "deleted_count": deleted_count
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting chats: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to delete chats", "details": str(e)}), 500