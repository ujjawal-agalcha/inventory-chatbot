import sqlite3
import logging
from config import DATABASE_PATH
from models import engine, SessionLocal, get_db, init_models

logger = logging.getLogger("database")

def get_connection():
    """Direct sqlite3 connection to canonical inventory.db if needed."""
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Idempotent database initialization using SQLAlchemy models."""
    logger.info("Initializing database at: %s", DATABASE_PATH)
    init_models()

if __name__ == "__main__":
    init_db()
