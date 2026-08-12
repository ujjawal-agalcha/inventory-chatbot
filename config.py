import os
from dotenv import load_dotenv

load_dotenv()

AUTHENTIK_BASE_URL = os.getenv("AUTHENTIK_BASE_URL", "")
AUTHENTIK_CLIENT_ID = os.getenv("AUTHENTIK_CLIENT_ID", "")
AUTHENTIK_CLIENT_SECRET = os.getenv("AUTHENTIK_CLIENT_SECRET", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me-in-production")

# Local development can bypass Authentik. Keep False in production.
DEV_AUTH_BYPASS = os.getenv("DEV_AUTH_BYPASS", "true").lower() == "true"

# Optional LLM configuration.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# RAG configuration.
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "2"))