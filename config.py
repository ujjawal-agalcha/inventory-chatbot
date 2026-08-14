import os
from dotenv import load_dotenv

load_dotenv()

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-3.5-flash")

# Authentik
AUTHENTIK_BASE_URL = os.getenv("AUTHENTIK_BASE_URL")
AUTHENTIK_CLIENT_ID = os.getenv("AUTHENTIK_CLIENT_ID")
AUTHENTIK_CLIENT_SECRET = os.getenv("AUTHENTIK_CLIENT_SECRET")
AUTHENTIK_REDIRECT_URI = os.getenv("AUTHENTIK_REDIRECT_URI")

SESSION_SECRET = os.getenv("SESSION_SECRET", "super-secret-key")