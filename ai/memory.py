import logging
from typing import List, Optional, Dict, Any
# pyrefly: ignore [missing-import]
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from ai.tools import detect_product

logger = logging.getLogger("ai.memory")


def resolve_product_with_context(
    message: str,
    conversation_history: Optional[List[dict]],
) -> Optional[dict]:
    """
    Resolve product considering current turn or previous context turns (pronouns).
    """
    # 1. Check current message first
    prod = detect_product(message)
    if prod:
        return prod

    # 2. Check for context / pronoun references ("it", "its", "this product", "the component")
    lower = message.lower()
    pronoun_words = [
        "it", "its", "this", "that", "the item", "the product", "the component",
        "who supplies", "who sells", "supplier", "how much is it", "what is its stock",
        "reorder it", "how many do we need", "what is the price", "who approved it",
        "how much did we spend", "what is the cost"
    ]

    has_pronoun = any(p in lower for p in pronoun_words)
    if not has_pronoun or not conversation_history:
        return None

    # Search backwards through conversation history
    for turn in reversed(conversation_history):
        content = turn.get("content", "")
        if not content:
            continue
        prod = detect_product(content)
        if prod:
            logger.info("Contextual match from previous turn: '%s' -> '%s'", content, prod["name"])
            return prod

    return None


def format_langchain_history(
    conversation_history: Optional[List[dict]],
    max_turns: int = 8,
) -> List[Any]:
    """Convert conversation turn dicts to LangChain Message objects."""
    messages = []
    if conversation_history:
        for turn in conversation_history[-max_turns:]:
            role = turn.get("role")
            content = turn.get("content", "")
            if not content:
                continue
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
    return messages
