# InboxAI

## Overview
InboxAI is a Retrieval-Augmented Generation (RAG) pipeline designed to revolutionize email data processing and analysis. Our system seamlessly integrates email fetching, processing, and storage capabilities, providing an intuitive web interface for advanced search and analytics.

## Project Structure

The project follows a modular architecture with these key components:

- `/data_pipeline`: Data ingestion and processing scripts
- `/backend`: Server implementation and RAG resources
- `/frontend`: User interface components and assets
- `/mlflow`: MLFlow tracking server (Docker-based)
- `/vector_db`: Chroma DB vector database setup

## Architecture
The system architecture is illustrated below:

![System Architecture](./data_pipeline/airflow/artifacts/project_arch.png)

## Getting Started
Refer to individual component directories for specific setup instructions and documentation.

### Component Documentation
- [Data Pipeline](./data_pipeline/README.md)
- [Backend](/backend/README.md)
- [Frontend](/frontend/README.md)
- [MLflow](/mlflow/README.md)
- [Vector DB](/vector_db/README.md)

### Installation Guide
