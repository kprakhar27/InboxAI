import logging
import re

import html2text
import pandas as pd
from bs4 import BeautifulSoup

# Initialize logging
logger = logging.getLogger(__name__)


class EmailPreprocessor:
    """
    Class for email preprocessing operations without spaCy dependency.
    """

    def __init__(self):
        """Initialize the EmailPreprocessor."""
        logger.info("Initializing EmailPreprocessor (lightweight version)")

    def load_data(self, file_path):
        """Load email data from parquet file."""
        try:
            df = pd.read_parquet(file_path)
            logger.info(f"Successfully loaded {len(df)} emails from {file_path}")
            return df
        except Exception as e:
            logger.error(f"Error loading data from {file_path}: {str(e)}")
            raise

    def preprocess(self, df):
        """Apply all preprocessing steps to the email DataFrame."""
        try:
            chunk_size = 1000
            chunks = [df[i : i + chunk_size] for i in range(0, len(df), chunk_size)]
            processed_chunks = []

            for i, chunk in enumerate(chunks):
                logger.info(f"Processing chunk {i+1}/{len(chunks)}")
                processed_chunk = self._preprocess_chunk(chunk)
                processed_chunks.append(processed_chunk)

            processed_df = pd.concat(processed_chunks, ignore_index=True)
            logger.info(f"Successfully preprocessed {len(processed_df)} emails")

            return processed_df

        except Exception as e:
            logger.error(f"Error in preprocessing: {str(e)}")
            raise

    def _preprocess_chunk(self, df_chunk):
        """Preprocess a chunk of the DataFrame."""
        required_columns = ["html_content", "plain_text", "subject"]
        for col in required_columns:
            if col not in df_chunk.columns:
                logger.warning(
                    f"Column {col} not found in DataFrame. Creating empty column."
                )
                df_chunk[col] = None

        # Extract plain text from HTML content
        df_chunk["extracted_text"] = df_chunk["html_content"].apply(
            self._extract_text_from_html
        )

        # Combine plain text and extracted text
        df_chunk["combined_text"] = df_chunk.apply(
            lambda row: (row["plain_text"] if pd.notna(row["plain_text"]) else "")
            + " "
            + (row["extracted_text"] if pd.notna(row["extracted_text"]) else ""),
            axis=1,
        )

        # Redact PII from text fields with regex only
        df_chunk["redacted_subject"] = df_chunk["subject"].apply(
            self._redact_pii_with_regex
        )
        df_chunk["redacted_text"] = df_chunk["combined_text"].apply(
            self._redact_pii_with_regex
        )

        # Clean up text (remove extra spaces, newlines, etc.)
        for col in ["redacted_subject", "redacted_text"]:
            df_chunk[col] = df_chunk[col].apply(
                lambda x: re.sub(r"\s+", " ", x).strip() if isinstance(x, str) else x
            )

        return df_chunk

    def _extract_text_from_html(self, html_content):
        """Extract plain text from HTML content."""
        if not isinstance(html_content, str) or pd.isna(html_content):
            return ""

        try:
            soup = BeautifulSoup(html_content, "html.parser")
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text(separator=" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()
            return text
        except Exception as e:
            logger.warning(f"Error extracting text from HTML: {e}")
            try:
                h = html2text.HTML2Text()
                h.ignore_links = True
                return h.handle(html_content)
            except:
                return ""

    def _redact_pii_with_regex(self, text):
        """Redact personally identifiable information using regex patterns."""
        if not isinstance(text, str) or pd.isna(text) or text == "":
            return ""

        try:
            # Email addresses
            text = re.sub(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]", text
            )

            # Phone numbers
            text = re.sub(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "[PHONE]", text)

            # URLs
            text = re.sub(
                r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
                "[URL]",
                text,
            )

            # SSNs
            text = re.sub(r"\b\d{3}[-]?\d{2}[-]?\d{4}\b", "[SSN]", text)

            # Credit card numbers
            text = re.sub(r"\b(?:\d[ -]*?){13,16}\b", "[CREDIT_CARD]", text)

            # Dates
            text = re.sub(
                r"\b(0?[1-9]|1[012])[- /.](0?[1-9]|[12][0-9]|3[01])[- /.](19|20)?\d\d\b",
                "[DATE]",
                text,
            )

            return text
        except Exception as e:
            logger.error(f"Error in regex redaction: {e}")
            return text
