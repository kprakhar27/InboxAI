# 📊 InboxAI MLflow

## 🧠 Description

This module sets up an MLflow Tracking Server to manage experiments, track runs, and log artifacts for InboxAI. The MLflow server is configured with a PostgreSQL backend for metadata storage and Google Cloud Storage (GCS) as the artifact store.

The deployment is automated via GitHub Actions and is containerized using Docker Compose for consistent, repeatable environments.

---

## 🧰 Prerequisites

### ☁️ Google Cloud

- GCS bucket for storing MLflow artifacts
- Service account with the following roles:
  - `roles/storage.admin`
  - `roles/logging.logWriter`

> 🔑 Files required:
> - `google_sa.json` – GCP service account key with access to the GCS bucket

---

### 🔐 GitHub Secrets Required

| Secret Name                 | Description                                              |
|----------------------------|----------------------------------------------------------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Contents of `google_sa.json`                         |
| `MLFLOW_ENV`               | Full contents of the `.env` file                         |
| `HOST`                     | Public IP of the deployment server                       |
| `SMTP_PASSWORD`            | Gmail App Password for deployment notifications          |

---

## 🛠️ Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/kprakhar27-inboxai.git
cd kprakhar27-inboxai/mlflow
```

---

### 2. Create `.env` File

Here is a template for the `.env` file. Update with your credentials and configuration:

```env
# MLflow Setup
MLFLOW_IMAGE=ghcr.io/mlflow/mlflow:latest
MLFLOW_PORT=7070
MLFLOW_TRACKING_USERNAME=yourmlflowuser
MLFLOW_TRACKING_PASSWORD=yourmlflowpass

# PostgreSQL (MLflow backend store)
DB_NAME=mlflow_db_name
DB_USER=mlflow_db_user
DB_PASSWORD=mlflow_db_pass
DB_HOST=<HOST_IP> 
DB_PORT=5432

# GCS (Artifact store)
ARTIFACT_ROOT=gs://gcs-email-landing-inbox-ai-bucket/mlflow-artifacts

# GCP Auth for MLflow + Logging
GCP_PROJECT_ID=gcp_project_id
GCP_CREDENTIAL_PATH=google_sa.json
GOOGLE_APPLICATION_CREDENTIALS=google_sa.json
```

Save this as `mlflow/.env`. The full content should also be stored in the GitHub secret `MLFLOW_ENV`.

---

## ⚙️ GitHub Actions Workflow

The CI/CD pipeline is defined in `.github/workflows/mlflow-setup.yml`. It includes the following:

1. Checkout the repository
2. Dynamically create the `google_sa.json` credentials file
3. Clean previous MLflow deployments (if any)
4. Copy new files to `$HOME/mlflow`
5. Populate the `.env` file from GitHub Secrets
6. Build and deploy the MLflow server via Docker Compose
7. Perform a health check on the MLflow `/health` endpoint
8. Send email notifications on success or failure

---

## ✅ Post-Deployment Health Check

The GitHub Actions workflow performs a health check on the MLflow server after deployment:

### 🔍 Example Check

```bash
curl http://<YOUR_SERVER_IP>:7070/health
```

Expected response:

```text
OK
```

If the server fails to respond with `OK`, the deployment is marked as failed and a notification email is sent.