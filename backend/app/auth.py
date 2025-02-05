from flask import request, jsonify, Blueprint
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import BadRequestKeyError
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
from sqlalchemy import text

from .models import Users, db
from .revoked_tokens import add_token_to_blocklist

auth_bp = Blueprint("auth", __name__)


# Test Route
@auth_bp.route("/", methods=["GET"])
def hello():
    return jsonify({"message": "Hello World"}), 200


@auth_bp.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")
        role = data.get(
            "role", "user"
        )  # Default to "user" if role is not provided

        if not username:
            return jsonify({"error": "Username is required"}), 400
        elif not password:
            return jsonify({"error": "Password is required"}), 400

        # Check if user already exists
        existing_user = Users.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({"error": "Username already exists"}), 400

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")

        try:
            new_user = Users(
                username=username, password_hash=hashed_password, role=role
            )
            access_token = create_access_token(identity=new_user.username)

            # Store the generated access token in the user's record
            new_user.access_token = access_token
            db.session.add(new_user)
            db.session.commit()

            return (
                jsonify(
                    {"message": "User registered successfully", "token": access_token}
                ),
                201,
            )
        except Exception as e:
            return (
                jsonify({"error": "Unable to register user", "detail": e.args[0]}),
                400,
            )
    except Exception as e:
        return jsonify({"error": "Server Error", "detail": e.args[0]}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    # Find user by username
    user = Users.query.filter_by(username=username).first()

    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"message": "Invalid credentials"}), 401

    # Create a new access token for this user
    access_token = create_access_token(identity=user.username)

    # Store the generated access token in the user's record
    user.access_token = access_token
    db.session.commit()  # Commit changes to save updated token

    return jsonify(access_token=access_token, role=user.role), 200


# Logout route - revoke access token and store it in PostgreSQL
@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    # Get the current token's unique identifier (JTI)
    jti = get_jwt()["jti"]

    # Add the JTI to the blocklist (revoking the token) by storing it in PostgreSQL
    add_token_to_blocklist(jti)

    return jsonify({"message": "Successfully logged out"}), 200


@auth_bp.route("/validate-token", methods=["GET"])
@jwt_required()
def validate_token():
    current_user = get_jwt_identity()
    return jsonify({"valid": True, "user": current_user}), 200