# InboxAI Backend

## Description

The backend of InboxAI is built using Flask, a lightweight WSGI web application framework in Python. It provides RESTful APIs for the frontend to interact with. The backend handles user authentication, data storage, and business logic. It uses SQLAlchemy for database interactions and Flask-JWT-Extended for handling JSON Web Tokens (JWT) for secure authentication. Additionally, Flask-CORS is used to enable Cross-Origin Resource Sharing (CORS) to allow the frontend to communicate with the backend seamlessly.

The deployed apis can be used using the endpoint https://backend.inboxai.tech

### Run Flask Backend

* Run the following commands to run the flask application in the terminal
* Make sure to cd into the **backend** directory

```bash
# Create virtual environment
python -m venv ./venv 
# Activate Virtual Environemt
source venv/bin/activate
# Install Requirements
pip install -r requirements.txt 
# Run App
python app.py
```