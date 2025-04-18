from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from sqlalchemy import text
from werkzeug.exceptions import BadRequestKeyError
from werkzeug.security import check_password_hash, generate_password_hash

from ..gcp_logger import log_route
from ..models import Users, db
from ..revoked_tokens import add_token_to_blocklist

auth_bp = Blueprint("auth", __name__)
logger = current_app.logger


@auth_bp.route("/", methods=["GET"])
@log_route
def hello():
    logger.info("Test route accessed")
    return jsonify({"message": "Hello World"}), 200


@auth_bp.route("/register", methods=["POST"])
@log_route
def register():
    """Register a new user."""
    logger.info("Starting user registration process")
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")
        role = data.get("role", "user")

        logger.info(f"Attempting to register user: {username} with role: {role}")

        if not username:
            logger.warning("Registration attempt without username")
            return jsonify({"error": "Username is required"}), 400
        elif not password:
            logger.warning("Registration attempt without password")
            return jsonify({"error": "Password is required"}), 400

        # Check if user exists
        existing_user = Users.query.filter_by(username=username).first()
        if existing_user:
            logger.warning(f"Registration attempted with existing username: {username}")
            return jsonify({"error": "Username already exists"}), 400

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")

        try:
            new_user = Users(
                username=username, password_hash=hashed_password, role=role
            )
            access_token = create_access_token(identity=new_user.username)
            new_user.access_token = access_token

            db.session.add(new_user)
            db.session.commit()

            logger.info(f"Successfully registered new user: {username}")
            return (
                jsonify(
                    {
                        "message": "User registered successfully",
                        "access_token": access_token,
                    }
                ),
                201,
            )

        except Exception as e:
            logger.error(f"Database error during registration: {str(e)}", exc_info=True)
            return jsonify({"error": "Unable to register user", "detail": str(e)}), 400

    except Exception as e:
        logger.error(f"Server error during registration: {str(e)}", exc_info=True)
        return jsonify({"error": "Server Error", "detail": str(e)}), 500


@auth_bp.route("/login", methods=["POST"])
@log_route
def login():
    """User login endpoint."""
    logger.info("Processing login request")
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        logger.info(f"Login attempt for user: {username}")

        user = Users.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            logger.warning(f"Failed login attempt for user: {username}")
            return jsonify({"message": "Invalid credentials"}), 401

        access_token = create_access_token(identity=user.username)
        user.access_token = access_token
        db.session.commit()

        logger.info(f"Successful login for user: {username}")
        return jsonify(access_token=access_token, role=user.role), 200

    except Exception as e:
        logger.error(f"Error during login: {str(e)}", exc_info=True)
        return jsonify({"error": "Login failed", "detail": str(e)}), 500


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
@log_route
def logout():
    """User logout endpoint."""
    try:
        current_user = get_jwt_identity()
        logger.info(f"Processing logout request for user: {current_user}")

        jti = get_jwt()["jti"]
        add_token_to_blocklist(jti)

        logger.info(f"Successfully logged out user: {current_user}")
        return jsonify({"message": "Successfully logged out"}), 200

    except Exception as e:
        logger.error(f"Error during logout: {str(e)}", exc_info=True)
        return jsonify({"error": "Logout failed", "detail": str(e)}), 500


@auth_bp.route("/validate-token", methods=["GET"])
@jwt_required()
@log_route
def validate_token():
    """Validate JWT token."""
    try:
        current_user = get_jwt_identity()
        logger.info(f"Token validation request for user: {current_user}")
        return jsonify({"valid": True, "user": current_user}), 200

    except Exception as e:
        logger.error(f"Token validation failed: {str(e)}", exc_info=True)
        return jsonify({"valid": False, "error": str(e)}), 401
