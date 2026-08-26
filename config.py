import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base directories and database path
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "inventory.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-3.5-flash")

# JWT Authentication
JWT_SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY",
    os.getenv("SESSION_SECRET", "inventory-chatbot-jwt-secret-key-production-32bytes-secure-2026"),
)
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

SESSION_SECRET = os.getenv("SESSION_SECRET", "inventory-chatbot-session-secret-key-32bytes-2026")

# MongoDB
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "inventory_chatbot")

