from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy

from .gcp_logger import setup_gcp_logging

db = SQLAlchemy()
jwt = JWTManager()


def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    # Setup GCP logging
    app.logger = setup_gcp_logging("inboxai-backend")
    app.logger.info("Starting InboxAI backend application")

    CORS(
        app,
        origins=["https://inboxai.tech", "http://localhost:3000"],
        supports_credentials=True,
    )

    db.init_app(app)
    jwt.init_app(app)

    with app.app_context():
        db.create_all()

        from .revoked_tokens import is_token_revoked
        from .routes.api import api_bp
        from .routes.auth import auth_bp

        app.register_blueprint(api_bp, url_prefix="/api")
        app.register_blueprint(auth_bp, url_prefix="/auth")

        # Configure JWT to check if the token is revoked by querying the database
        @jwt.token_in_blocklist_loader
        def check_if_token_revoked(jwt_header, jwt_payload):
            return is_token_revoked(jwt_payload)

    return app
