from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, Field, model_validator


class Attachment(BaseModel):
    filename: str
    mime_type: str
    size: Optional[int] = None


class EmailSchema(BaseModel):
    message_id: str = Field(..., description="Unique identifier for the email")
    from_email: str
    to: List[str] = Field(..., description="List of primary recipients")
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    subject: str = Field(..., description="Subject of the email")
    date: str = Field(..., description="Timestamp when the email was sent")
    content: Optional[str] = None
    plain_text: Optional[str] = None
    html: Optional[str] = None
    attachments: Optional[List[Attachment]] = None
    thread_id: Optional[str] = None
    labels: Optional[List[str]] = None

    @model_validator(mode="before")
    @classmethod
    def set_content(cls, data: dict) -> dict:
        """Use plain_text if available, otherwise use html, or return None"""
        plain_text = data.get("plain_text")
        html = data.get("html")
        data["content"] = plain_text or html or data.get("content")
        return data

    class Config:
        from_attributes = True  # Updated from orm_mode
