import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from flask_sqlalchemy import SQLAlchemy
from google_auth_oauthlib.flow import Flow
from pipelines.email_pipeline import EmailPipeline

db = SQLAlchemy()
flow = Flow.from_client_secrets_file(
    "/Users/pradnyeshchoudhari/IE 7374 - LOCAL/InboxAI/backend/credentials.json",
    scopes=[
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/userinfo.email",
    ],
    redirect_uri=os.environ.get("REDIRECT_URI"),
)

email = "pc612001@gmail.com"
start_date = "2025/02/01"
end_date = "2025/02/01"

# Initialize pipeline
pipeline = EmailPipeline(db.session, email, flow.client_config)

# Store both emails and threads
email_total, email_saved = pipeline.process_emails(start_date, end_date)
thread_total, thread_saved = pipeline.process_threads(start_date, end_date)
