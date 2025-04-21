# 🧠 InboxAI Vector Database (ChromaDB)

## 📦 Description

The Vector DB module of InboxAI runs [ChromaDB](https://www.trychroma.com/) as the vector database backend for storing and querying email embeddings. ChromaDB enables high-performance semantic search and similarity matching using OpenAI-generated embeddings.

This service is deployed via Docker Compose and is integrated with Airflow and MLflow for full-stack experiment tracking and query processing.

---

## 🧰 Prerequisites

### 🧾 System & Stack Requirements

- Docker and Docker Compose installed on the server
- Port `8000` open and available on the deployment host
- External Docker network `chroma_network` (shared with Airflow)

### 🔐 GitHub Secrets Required

| Secret Name       | Description                          |
|------------------|--------------------------------------|
| `HOST`           | Public IP or DNS of the target server |
| `SMTP_PASSWORD`  | Gmail App Password for notifications  |

---

## 🛠️ Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/kprakhar27-inboxai.git
cd kprakhar27-inboxai/vector_db
```

---

### 2. External Docker Network

Ensure a shared Docker network exists so Chroma can interact with other services (e.g. Airflow):

```bash
docker network create chroma_network
```

---

### 3. Start Chroma Vector DB

```bash
docker compose up --build -d
```

This starts the Chroma server at:  
📍 `http://localhost:8000`

---

### 4. Health Check

You can check Chroma's health via:

```bash
curl http://localhost:8000/api/v1/heartbeat
```

Expected response: HTTP `200 OK`

---

## ⚙️ GitHub Actions Workflow

The CI/CD pipeline for ChromaDB is defined in `.github/workflows/vector-setup.yml`. It includes the following steps:

1. Checkout repository code
2. Perform a health check on the Airflow scheduler & triggerer
3. Clean up old ChromaDB deployment (if exists)
4. Copy and deploy updated `docker-compose.yml` for Chroma
5. Verify health of ChromaDB via `/api/v2/heartbeat`
6. Send email notifications on success or failure

---

## ✅ Post-Deployment Health Check

The workflow checks for successful deployment using:

```bash
curl -s -o /dev/null -w "%{http_code}" http://<HOST>:8000/api/v2/heartbeat
```

Expected HTTP status: `200`

If the check fails, the workflow exits and sends an error alert to the configured email.