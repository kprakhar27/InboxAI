
import os
import sys
import uuid
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import Users, Chat, Message
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

load_dotenv(".env")

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
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()

def register_and_login(client):
    client.post("/auth/register", json={
        "username": "apiuser",
        "password": "testpass"
    })
    res = client.post("/auth/login", json={
        "username": "apiuser",
        "password": "testpass"
    })
    return res.get_json()["access_token"]

# --- /api/redirect ---
def test_redirect_url(client):
    response = client.get("/api/redirect?code=1234&state=abcd")
    assert response.status_code == 301
    assert "https://inboxai.tech/#/redirect" in response.location

# --- /api/addprofile ---
def test_addprofile(client):
    token = register_and_login(client)
    response = client.post("/api/addprofile", headers={
        "Authorization": f"Bearer {token}"
    })
    assert response.status_code == 200
    assert response.get_json()["message"] == "Hello World"

def test_addprofile_unauthorized(client):
    response = client.post("/api/addprofile")
    assert response.status_code == 401

# --- /api/createchat ---
def test_create_chat(client):
    token = register_and_login(client)
    response = client.post("/api/createchat", json={"name": "My Test Chat"}, headers={
        "Authorization": f"Bearer {token}"
    })
    assert response.status_code == 201
    data = response.get_json()
    assert data["name"] == "My Test Chat"
    assert "chat_id" in data

def test_create_chat_default_name(client):
    token = register_and_login(client)
    response = client.post("/api/createchat", headers={
        "Authorization": f"Bearer {token}"
    })
    assert response.status_code == 201
    assert response.get_json()["name"] == "New Chat"

# --- /api/getchats ---
def test_get_chats(client):
    token = register_and_login(client)
    for i in range(2):
        client.post("/api/createchat", json={"name": f"Chat {i}"}, headers={
            "Authorization": f"Bearer {token}"
        })
    response = client.get("/api/getchats", headers={
        "Authorization": f"Bearer {token}"
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 2
    assert all("chat_id" in chat for chat in data["chats"])

def test_get_chats_empty(client):
    token = register_and_login(client)
    response = client.get("/api/getchats", headers={
        "Authorization": f"Bearer {token}"
    })
    assert response.status_code == 200
    assert response.get_json()["total"] == 0

# --- /api/inferencefeedback ---
def test_inference_feedback(client):
    token = register_and_login(client)
    user = Users.query.filter_by(username="apiuser").first()
    chat = Chat(user_id=user.id, name="Chat for Feedback")
    db.session.add(chat)
    db.session.commit()
    msg = Message(
        chat_id=chat.chat_id,
        user_id=user.id,
        rag_id=uuid.uuid4(),
        query="How are you?",
        response="I'm fine!",
        context="",
        response_time_ms=123,
        is_toxic=False
    )
    db.session.add(msg)
    db.session.commit()
    response = client.post("/api/inferencefeedback", json={
        "message_id": str(msg.message_id),
        "feedback": True
    }, headers={
        "Authorization": f"Bearer {token}"
    })
    assert response.status_code == 200
    assert response.get_json()["feedback"] is True

def test_inference_feedback_invalid_payload(client):
    token = register_and_login(client)
    response = client.post("/api/inferencefeedback", json={
        "message_id": "invalid"
    }, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400
    assert "error" in response.get_json()

def test_feedback_wrong_user(client):
    token_a = register_and_login(client)
    user_a = Users.query.filter_by(username="apiuser").first()
    chat = Chat(user_id=user_a.id, name="Chat A")
    db.session.add(chat)
    db.session.commit()
    msg = Message(
        chat_id=chat.chat_id,
        user_id=user_a.id,
        rag_id=uuid.uuid4(),
        query="test", response="test", context="", response_time_ms=0, is_toxic=False
    )
    db.session.add(msg)
    db.session.commit()

    client.post("/auth/register", json={"username": "userb", "password": "testpass"})
    login_b = client.post("/auth/login", json={"username": "userb", "password": "testpass"})
    token_b = login_b.get_json()["access_token"]

    response = client.post("/api/inferencefeedback", json={
        "message_id": str(msg.message_id),
        "feedback": True
    }, headers={"Authorization": f"Bearer {token_b}"})

    assert response.status_code == 404
    assert response.get_json()["error"] == "Message not found or access denied"
