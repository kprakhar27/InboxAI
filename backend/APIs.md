# API Endpoint Documentation

This document lists all API endpoints exposed by the Flask application, including input and output formats.

---

## 🔐 Auth Routes

### `POST /auth/register`
**Request Body:**
```json
{
  "username": "string",
  "password": "string",
  "role": "string"  // optional
}
```
**Response:**
```json
{
  "message": "User registered successfully",
  "access_token": "jwt-token"
}
```

### `POST /auth/login`
**Request Body:**
```json
{
  "username": "string",
  "password": "string"
}
```
**Response:**
```json
{
  "access_token": "jwt-token",
  "role": "string"
}
```

### `POST /auth/logout`
**Headers:** `Authorization: Bearer <token>`
**Response:**
```json
{
  "message": "Successfully logged out"
}
```

### `GET /auth/validate-token`
**Headers:** `Authorization: Bearer <token>`
**Response:**
```json
{
  "valid": true,
  "user": "username"
}
```

---

## 📧 Google Account Routes

### `POST /api/getgmaillink`
**Headers:** `Authorization: Bearer <token>`
**Response:**
```json
{
  "authorization_url": "string",
  "state": "string"
}
```

### `POST /api/savegoogletoken`
**Headers:** `Authorization: Bearer <token>`
**Request Body:**
```json
{
  "auth_url": "string"
}
```
**Response:**
```json
{
  "message": "Successfully added/updated email: example@gmail.com"
}
```

### `GET /api/getconnectedaccounts`
**Headers:** `Authorization: Bearer <token>`
**Response:**
```json
{
  "accounts": [
    {
      "email": "string",
      "expires_at": "ISO8601",
      "run_status": "string",
      "last_read": "ISO8601 or string",
      "total_emails_processed": number
    }
  ],
  "total_accounts": number
}
```

### `POST /api/refreshemails`
**Headers:** `Authorization: Bearer <token>`
**Response:**
```json
{
  "message": "Triggered email refresh for N accounts",
  "successful": ["email1", "email2"],
  "failed": [
    {
      "email": "string",
      "error": "string"
    }
  ]
}
```

### `POST /api/removeemail`
**Headers:** `Authorization: Bearer <token>`
**Request Body:**
```json
{
  "email": "string"
}
```
**Response:**
```json
{
  "message": "Successfully triggered email removal pipeline, user: <uuid>, email: <email>"
}
```

---

## 💬 Chat and Inference Routes

### `POST /api/createchat`
**Headers:** `Authorization: Bearer <token>`
**Request Body (optional):**
```json
{
  "name": "Custom Chat Name"
}
```
**Response:**
```json
{
  "chat_id": "uuid",
  "name": "string",
  "created_at": "ISO8601"
}
```

### `GET /api/getchats`
**Headers:** `Authorization: Bearer <token>`
**Response:**
```json
{
  "chats": [
    {
      "chat_id": "uuid",
      "name": "string",
      "created_at": "ISO8601"
    }
  ],
  "total": number
}
```

### `GET /api/getmessages/<chat_id>`
**Headers:** `Authorization: Bearer <token>`
**Response:**
```json
{
  "chat_id": "uuid",
  "messages": [
    {
      "message_id": "uuid",
      "query": "string",
      "response": "string",
      "rag_id": "uuid",
      "response_time_ms": number,
      "feedback": boolean,
      "is_toxic": boolean,
      "created_at": "ISO8601"
    }
  ],
  "total": number
}
```

### `POST /api/inferencefeedback`
**Headers:** `Authorization: Bearer <token>`
**Request Body:**
```json
{
  "message_id": "uuid",
  "feedback": true
}
```
**Response:**
```json
{
  "message": "Feedback recorded successfully",
  "message_id": "uuid",
  "feedback": true
}
```

### `POST /api/deletechats`
**Headers:** `Authorization: Bearer <token>`
**Response:**
```json
{
  "message": "Successfully deleted N chats",
  "deleted_count": number
}
```

### `POST /api/getinference`
**Headers:** `Authorization: Bearer <token>`
**Request Body:**
```json
{
  "query": "string",
  "chat_id": "uuid",
  "rag_id": "uuid"
}
```
**Response:**
```json
{
  "message_id": "uuid",
  "response": "string",
  "rag_id": "uuid",
  "query": "string",
  "response_time_ms": number,
  "is_toxic": boolean
}
```

---

## 📚 RAG Sources

### `GET /api/ragsources`
**Headers:** `Authorization: Bearer <token>`
**Response:**
```json
{
  "sources": [
    {
      "rag_id": "uuid",
      "name": "string"
    }
  ],
  "total": number
}
```

---

## 🔁 Redirects

### `GET /api/redirect`
**Query Params:** OAuth state params
**Redirects to:** `https://inboxai.tech/#/redirect?...`

---
