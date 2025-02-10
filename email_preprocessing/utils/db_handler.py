import json
import logging
from threading import Lock

import psycopg2
from config.settings import DB_CONFIG, TOKEN_TABLE

db_lock = Lock()


class DatabaseHandler:
    @staticmethod
    def get_connection():
        """Establishes a connection to the PostgreSQL database."""
        try:
            return psycopg2.connect(**DB_CONFIG)
        except Exception as e:
            logging.error(f"Error connecting to database: {e}")
            return None

    @staticmethod
    def fetch_token(email):
        """Fetches the token for a given email."""
        try:
            with db_lock:
                conn = DatabaseHandler.get_connection()
                if not conn:
                    return None

                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT token FROM {TOKEN_TABLE} WHERE email = %s", (email,)
                    )
                    result = cur.fetchone()

                conn.close()

                if result:
                    return result[0]  # JSONB is returned as a dict in psycopg2
                return None
        except Exception as e:
            logging.error(f"Error retrieving token: {e}")
            return None

    @staticmethod
    def save_token(email, token):
        """Saves or updates the token for a given email."""
        try:
            with db_lock:
                conn = DatabaseHandler.get_connection()
                if not conn:
                    return

                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        INSERT INTO {TOKEN_TABLE} (email, token, updated_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (email) DO UPDATE 
                        SET token = EXCLUDED.token, updated_at = CURRENT_TIMESTAMP;
                        """,
                        (email, json.dumps(token)),  # Ensuring token is JSONB
                    )
                conn.commit()
                conn.close()
                logging.info(f"Token saved for email: {email}")
        except Exception as e:
            logging.error(f"Error saving token: {e}")
