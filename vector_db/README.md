# Chroma DB for Storing Embeddings

This repository contains the setup for Chroma DB, which is used for storing embeddings.

## Steps to Run with Docker Compose

1. **Build and Start the Containers**
   Run the following command to build and start the Docker containers:

   ```sh
   docker-compose up --build
   ```

2. **Access the Application**
   Once the containers are up and running, you can access the application on `http://localhost:8000`.

3. **Ensure Airflow is Running**
   Make sure the Airflow Docker Compose setup is running before executing the above steps.