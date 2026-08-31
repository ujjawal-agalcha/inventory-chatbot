import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base directories
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "inventory.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"
UPLOADS_DIR = DATA_DIR / "uploads"
EXPORTS_DIR = DATA_DIR / "exports"
SAMPLE_DIR = DATA_DIR / "sample"

FRONTEND_DIR = BASE_DIR / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"

# Ensure runtime directories exist
for directory in [KNOWLEDGE_DIR, UPLOADS_DIR, EXPORTS_DIR, SAMPLE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Gemini AI Settings
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
