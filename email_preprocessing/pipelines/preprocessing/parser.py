import logging
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime

from email_preprocessing.pipelines.preprocessing.cleaner import clean_text, html_to_text


def process_email_content(msg):
    """
    Process email content and return cleaned text and attachment info.

    Args:
        msg: An email.message.Message object.

    Returns:
        A tuple containing:
        - The cleaned email body text (str).
        - A list of attachments (List[Dict]).
    """
    body_text = ""
    html_text = ""
    attachments = []

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue

            filename = part.get_filename()
            if filename:
                attachments.append(
                    {
                        "filename": filename,
                        "content_type": part.get_content_type(),
                        "size": (
                            len(part.get_payload(decode=True))
                            if part.get_payload()
                            else 0
                        ),
                    }
                )
                continue

            content_type = part.get_content_type()
            try:
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                text_candidate = payload.decode(errors="replace")

                if content_type == "text/plain":
                    body_text = clean_text(text_candidate)
                    break
                elif content_type == "text/html":
                    html_text = text_candidate
            except Exception as e:
                logging.error(f"Error processing part: {e}")
                continue
    else:
        content_type = msg.get_content_type()
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                text_candidate = payload.decode(errors="replace")
                if content_type == "text/plain":
                    body_text = clean_text(text_candidate)
                elif content_type == "text/html":
                    html_text = text_candidate
        except Exception as e:
            logging.error(f"Error processing content: {e}")

    if not body_text and html_text:
        body_text = clean_text(html_to_text(html_text))

    return body_text, attachments


def extract_email_metadata(msg):
    """
    Extract comprehensive metadata from an email message.

    Args:
        msg: An email.message.Message object.

    Returns:
        A dictionary containing email metadata.
    """
    from_header = msg.get("From", "")
    sender_name, sender_email = parseaddr(from_header)
    to_header = msg.get("To", "")
    _, recipient_email = parseaddr(to_header)

    received_date = parsedate_to_datetime(msg.get("Date")) if msg.get("Date") else None

    return {
        "message_id": msg.get("Message-ID", "").strip("<>"),
        "sender": {
            "email": sender_email,
            "name": sender_name,
            "domain": sender_email.split("@")[-1] if "@" in sender_email else "unknown",
        },
        "recipient": {
            "email": recipient_email,
            "domain": (
                recipient_email.split("@")[-1] if "@" in recipient_email else "unknown"
            ),
        },
        "subject": msg.get("Subject", ""),
        "date": received_date.isoformat() if received_date else None,
        "thread_id": msg.get("Thread-ID", ""),
        "in_reply_to": msg.get("In-Reply-To", ""),
        "references": msg.get("References", "").split(),
        "importance": msg.get("Importance", "normal"),
    }
