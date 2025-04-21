# InboxAI Backend

## Description

The backend of InboxAI is built using Flask, a lightweight WSGI web application framework in Python. It provides RESTful APIs for the frontend to interact with. The backend handles user authentication, data storage, and business logic. It uses SQLAlchemy for database interactions and Flask-JWT-Extended for handling JSON Web Tokens (JWT) for secure authentication. Additionally, Flask-CORS is used to enable Cross-Origin Resource Sharing (CORS) to allow the frontend to communicate with the backend seamlessly.

The deployed apis can be used using the endpoint: https://test.inboxai.tech

Detailed steps for installing and authenticating the Google Cloud SDK (`gcloud`), setting up the Artifact Registry repository, and creating the necessary service account with appropriate roles.


## 📁 Project Structure


```bash
kprakhar27-inboxai/
    ├── README.md
    ├── backend/
    │   ├── README.md
    │   ├── __init__.py
    │   ├── config.py
    │   ├── Dockerfile
    │   ├── POSTGRES_DDLS.sql
    │   ├── pytest.ini
    │   ├── requirements.txt
    │   ├── app/
    │   │   ├── __init__.py
    │   │   ├── gcp_logger.py
    │   │   ├── models.py
    │   │   ├── revoked_tokens.py
    │   │   ├── rag/
    │   │   │   ├── README.md
    │   │   │   ├── __init__.py
    │   │   │   ├── CRAGPipeline.py
    │   │   │   ├── models.py
    │   │   │   ├── RAGConfig.py
    │   │   │   └── RAGPipeline.py
    │   │   └── routes/
    │   │       ├── api.py
    │   │       ├── auth.py
    │   │       └── get_flow.py
    │   └── tests/
    │       ├── test_api.py
    │       └── test_route.py
    └── .github/
        └── workflows/
            └── backend-deploy.yml
```


## 🧰 Prerequisites

- Google Cloud Project with billing enabled
- Artifact Registry repository
- Cloud Run enabled
- Service account with the following roles:
  - `roles/artifactregistry.writer`
  - `roles/run.admin`
  - `roles/iam.serviceAccountUser`
- Service account key (`key.json`)
- GitHub repository with secrets:
  - `GCP_SA_KEY`
  - `GOOGLE_CREDENTIALS`
  - `GOOGLE_APPLICATION_CREDENTIALS`
  - `BACKEND_ENV`
  - `SMTP_PASSWORD`

---

## 🛠️ Setup Instructions

### 1. Install Google Cloud SDK

Follow the official guide to install the Google Cloud SDK:  
[Installing Cloud SDK](https://cloud.google.com/sdk/docs/install)

After installation, initialize the SDK:

```bash
gcloud init
```

### 2. Authenticate with Google Cloud

For user account authentication:

```bash
gcloud auth login
```

### 3. Set the Active Project

```bash
gcloud config set project YOUR_PROJECT_ID
```

### 4. Enable Required APIs

```bash
gcloud services enable artifactregistry.googleapis.com run.googleapis.com
```

### 5. Create Artifact Registry Repository

```bash
gcloud artifacts repositories create flask-repo \
  --repository-format=docker \
  --location=us-central1 \
  --description="Docker repository for Flask app"
```

### 6. Create Service Account and Assign Roles

```bash
# Create the service account
gcloud iam service-accounts create github-ci-cd \
  --display-name="GitHub CI/CD Service Account"

# Assign roles to the service account
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:github-ci-cd@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:github-ci-cd@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud iam service-accounts add-iam-policy-binding \
  123456789-compute@developer.gserviceaccount.com \
  --member="serviceAccount:github-ci-cd@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

### 7. Generate and Download Service Account Key

```bash
gcloud iam service-accounts keys create key.json \
  --iam-account=github-ci-cd@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

**Important:** Keep this `key.json` file secure.

### 8. Configure GitHub Secrets

- Navigate to your GitHub repository.
- Go to `Settings` > `Secrets and variables` > `Actions`.
- Add the following secrets:
  - `GCP_SA_KEY`: Contents of `key.json`
  - `GOOGLE_CREDENTIALS`: Contents of OAuth credentials JSON for Gmail APIs
  - `GOOGLE_APPLICATION_CREDENTIALS`: Contents of GCS service account JSON for Logging
  - `BACKEND_ENV`: Full contents of your `.env` file
  - `SMTP_PASSWORD`: Your Gmail app password for deployment notifications

---

## 🔐 Sample .env File

Here is a placeholder example of what your `.env` file might look like:

```env
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=your_db_host
DB_PORT=5432

SECRET_KEY=your_secret_key
JWT_SECRET_KEY=your_jwt_secret_key

REDIRECT_URI=https://test.inboxai.com/api/redirect
CREDENTIAL_PATH_FOR_GMAIL_API=credentials.json
GOOGLE_APPLICATION_CREDENTIALS=google_sa.json

AIRFLOW_API_IP=your_airflow_ip
AIRFLOW_API_USER=your_airflow_user
AIRFLOW_API_PASSWORD=your_airflow_password
AIRFLOW_API_PORT=8080

MLFLOW_TRACKING_URI=http://your_mlflow_user:your_mlflow_password@your_mlflow_host:7070
MLFLOW_USERNAME=your_mlflow_user
MLFLOW_PASSWORD=your_mlflow_password

TEST_DATASET_PATH=rag_model/qa_data
EMBEDDING_MODEL=text-embedding-3-small

OPENAI_API_KEY=your_openai_api_key
GROQ_API_KEY=your_groq_api_key
LLM_MODEL=llama3-8b-8192
TOP_K=3
TEMPERATURE=0

CHROMA_COLLECTION=test
CHROMA_HOST=your_chroma_host
CHROMA_PORT=8000

```

Update the values according to your configuration and save this as `backend/.env`. Store the full file content in the `BACKEND_ENV` GitHub secret.

---

## ⚙️ GitHub Actions Workflow

The CI/CD pipeline is defined in `.github/workflows/deploy.yml` and includes the following:

1. Checkout code
2. Dynamically generate `credentials.json`, `google_sa.json`, `.env`
3. Run pre-deployment tests with `pytest`
4. Authenticate with GCP using `google-github-actions/auth`
5. Build and push Docker image to Artifact Registry
6. Deploy container to Cloud Run
7. Health check on `/auth` endpoint
8. Email notification of success or failure

---

## 🌐 Custom Domain Mapping

To map a custom domain to your Cloud Run service:

```bash
gcloud run domain-mappings create \
  --service=flask-api \
  --domain=your.custom.domain \
  --platform=managed \
  --project=YOUR_PROJECT_ID
```

Then update your DNS records as instructed. GCP will handle SSL provisioning automatically.

---

## 📡 API Routes Documentation

### 🔐 Auth Routes
- `GET /auth/` – Health check endpoint
- `POST /auth/register` – Register a new user
- `POST /auth/login` – User login
- `POST /auth/logout` – User logout (requires JWT)
- `GET /auth/validate-token` – Validate current JWT (requires JWT)

### 📧 Google Account Routes
- `POST /api/getgmaillink` – Get Google OAuth authorization link (JWT required)
- `POST /api/savegoogletoken` – Save Google OAuth token (JWT required)
- `GET /api/getconnectedaccounts` – List connected Gmail accounts (JWT required)
- `POST /api/refreshemails` – Trigger email refresh DAG in Airflow (JWT required)
- `POST /api/removeemail` – Trigger email deletion DAG in Airflow (JWT required)

### 💬 Chat and Inference Routes
- `POST /api/createchat` – Create new chat session (JWT required)
- `GET /api/getchats` – Get list of chat sessions (JWT required)
- `GET /api/getmessages/<chat_id>` – Get messages for a chat (JWT required)
- `POST /api/getinference` – Send query and get RAG response (JWT required)
- `POST /api/inferencefeedback` – Submit feedback for a message (JWT required)
- `POST /api/deletechats` – Delete all chats and messages (JWT required)

### 📚 RAG Sources
- `GET /api/ragsources` – List all available RAG sources (JWT required)

### 🔁 Redirects
- `GET /api/redirect` – Redirect to frontend with OAuth params

---

## 🧪 Testing

### Running Unit Tests

```bash
pytest backend/tests/
```

### Post-Deployment Health Check

The GitHub Actions workflow performs a health check on the `/auth` endpoint using `curl`.

Certainly! Here's an updated `README.md` that includes detailed steps for installing and authenticating the Google Cloud SDK (`gcloud`), setting up the Artifact Registry repository, and creating the necessary service account with appropriate roles.



