import logging
import re

from bs4 import BeautifulSoup


def clean_text(payload):
    """
    Clean and normalize text content from emails.

    Args:
        payload: The raw text content (can be bytes or str).

    Returns:
        The cleaned and normalized text.
    """
    if not payload:
        return ""
    try:
        if isinstance(payload, bytes):
            text = payload.decode(errors="replace")
        else:
            text = str(payload)

        # Remove email forwarding patterns
        text = re.sub(r"(?m)^>.*$", "", text)
        # Remove email signatures
        text = re.sub(r"--\s*\n.*$", "", text, flags=re.DOTALL)
        # Remove URLs
        text = re.sub(
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
            "",
            text,
        )
        # Remove HTML tags
        text = re.sub("<[^<]+?>", "", text)
        # Remove HTML entities
        text = re.sub("&[a-zA-Z]+;", " ", text)
        # Normalize whitespace
        text = " ".join(text.split())
        return text.strip()
    except Exception as e:
        logging.error(f"Warning during text cleaning: {e}")
        return ""


def html_to_text(html):
    """
    Convert HTML content to plain text using BeautifulSoup.

    Args:
        html: The HTML content.

    Returns:
        The plain text extracted from the HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ", strip=True)
