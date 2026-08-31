import logging
# pyrefly: ignore [missing-import]
from langchain_google_genai import ChatGoogleGenerativeAI

from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("ai.gemini")


def get_llm(temperature: float = 0.2) -> ChatGoogleGenerativeAI:
    """Create the LangChain Gemini client."""
    clean_model = (
        GEMINI_MODEL.replace("models/", "")
        if GEMINI_MODEL
        else "gemini-3.5-flash"
    )
    return ChatGoogleGenerativeAI(
        model=clean_model,
        google_api_key=GEMINI_API_KEY,
        temperature=temperature,
    )
