import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import Users  # Assuming you have this model
from dotenv import load_dotenv
from flask import Flask
from werkzeug.security import generate_password_hash

load_dotenv(dotenv_path=".env")

class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = "test-secret"
    SECRET_KEY = "test-secret"

@pytest.fixture
def client():
    app = create_app(TestConfig)

    with app.app_context():
        print("USING DB:", app.config["SQLALCHEMY_DATABASE_URI"])
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()
        
def register_user(client, username="testuser", password="testpass", role="user"):
    return client.post("/auth/register", json={
        "username": username,
        "password": password,
        "role": role
    })

def login_user(client, username="testuser", password="testpass"):
    return client.post("/auth/login", json={
        "username": username,
        "password": password
    })

# --- Base Test ---

def test_home(client):
    response = client.get("/auth/")
    assert response.status_code == 200
    assert response.data == b'{"message":"Hello World"}\n'

# --- Register Tests ---

def test_register_success(client):
    response = register_user(client)
    assert response.status_code == 201
    data = response.get_json()
    assert "access_token" in data

def test_register_missing_username(client):
    response = client.post("/auth/register", json={"password": "testpass"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "Username is required"

def test_register_missing_password(client):
    response = client.post("/auth/register", json={"username": "user"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "Password is required"

def test_register_duplicate_user(client):
    register_user(client)
    response = register_user(client)
    assert response.status_code == 400
    assert response.get_json()["error"] == "Username already exists"

# --- Login Tests ---

def test_login_success(client):
    register_user(client)
    response = login_user(client)
    assert response.status_code == 200
    assert "access_token" in response.get_json()

def test_login_invalid_credentials(client):
    response = login_user(client)
    assert response.status_code == 401
    assert response.get_json()["message"] == "Invalid credentials"

# --- Token Validation and Logout ---

def test_validate_token(client):
    register_user(client)
    login_res = login_user(client)
    token = login_res.get_json()["access_token"]

    response = client.get(
        "/auth/validate-token",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.get_json()["valid"] is True

def test_logout_success(client, monkeypatch):
    register_user(client)
    login_res = login_user(client)
    token = login_res.get_json()["access_token"]

    # Mock token revocation
    monkeypatch.setattr("app.routes.auth.add_token_to_blocklist", lambda jti: None)

    response = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.get_json()["message"] == "Successfully logged out"
    