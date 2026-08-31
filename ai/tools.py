import re
import logging
from typing import List, Optional, Any
from excel.normalizer import normalize_text
from database.repositories.product_repository import (
    get_product_by_name_or_norm,
    get_all_products_from_mongo,
    search_products_in_mongo,
)

logger = logging.getLogger("ai.tools")

# ============================================================
# INTENT KEYWORDS
# ============================================================

STOCK_KEYWORDS = [
    "stock", "inventory", "available", "availability", "quantity", "units",
    "how many", "do we have", "have we got", "in stock", "count", "left", "remaining"
]

LOW_STOCK_KEYWORDS = [
    "low stock", "low-stock", "lowstock", "low in stock", "low on stock",
    "shortage", "below minimum", "under minimum", "needs reorder",
    "need reorder", "running low", "running out", "out of stock", "zero stock"
]

REORDER_KEYWORDS = [
    "reorder", "re-order", "re order", "order more", "place order",
    "create order", "replenish", "restock", "re-stock", "purchase more"
]

SUPPLIER_KEYWORDS = [
    "supplier", "who supplies", "supplied by", "vendor", "where to buy",
    "who sells", "distributor", "market", "who approved", "approved by"
]

EXPENSE_KEYWORDS = [
    "expense", "expenses", "spend", "spent", "cost", "total amount",
    "purchased", "how much did we buy", "price", "unit price", "paid"
]

REQUIREMENT_KEYWORDS = [
    "requirement", "requirements", "required", "needed", "order status",
    "pending", "fulfilled", "requisition", "procurement"
]

ALL_INVENTORY_KEYWORDS = [
    "all inventory", "all products", "all components", "show inventory",
    "show everything", "list inventory", "list all", "show all", "view all",
    "entire inventory", "all items"
]


def has_keyword(text: str, keywords: List[str]) -> bool:
    lower = text.lower()
    return any(k in lower for k in keywords)


def detect_product(message: str) -> Optional[dict]:
    """
    Resolve a product from the user's natural-language message.
    1. Direct match with get_product_by_name_or_norm(message)
    2. Substring & alias matching against all products with word-boundary awareness
    3. Token-based intelligent search
    """
    if not message:
        return None

    norm = normalize_text(message)
    if not norm:
        return None

    ignore_words = {"hi", "hello", "hey", "thanks", "thank you", "bye", "ok", "okay", "yes", "no", "help", "who are you"}
    if norm in ignore_words:
        return None

    # 1. Direct lookup
    direct = get_product_by_name_or_norm(message)
    if direct:
        logger.info("Direct product match: '%s'", direct["name"])
        return direct

    # 2. Check all products for alias or substring match with word-boundary awareness
    all_items = get_all_products_from_mongo()
    sorted_items = sorted(all_items, key=lambda x: len(x.get("name", "")), reverse=True)

    for item in sorted_items:
        item_norm = item.get("normalized_name", "")
        item_name_lower = item.get("name", "").lower()

        if item_norm and len(item_norm) >= 3 and re.search(r'\b' + re.escape(item_norm) + r'\b', norm):
            logger.info("Found product by normalized name in query: '%s'", item["name"])
            return item

        if item_name_lower and len(item_name_lower) >= 3 and re.search(r'\b' + re.escape(item_name_lower) + r'\b', message.lower()):
            logger.info("Found product by name substring in query: '%s'", item["name"])
            return item

        for alias in item.get("aliases", []):
            alias_norm = normalize_text(alias)
            if alias_norm and len(alias_norm) >= 3 and alias_norm not in ignore_words:
                if re.search(r'\b' + re.escape(alias_norm) + r'\b', norm):
                    logger.info("Found product by alias in query: '%s' -> '%s'", alias, item["name"])
                    return item

    # 3. Intelligent search via token intersection
    search_results = search_products_in_mongo(message, limit=3)
    if search_results:
        best = search_results[0]
        best_norm = best.get("normalized_name", "")
        best_tokens = set(best_norm.split())
        stop_words = {
            "how", "many", "much", "is", "are", "there", "in", "stock", "available",
            "do", "we", "have", "got", "the", "a", "an", "what", "which", "please",
            "tell", "me", "about", "show", "give", "current", "units", "left", "who", "supplies",
            "hi", "hello", "hey", "can", "you", "i", "need"
        }
        msg_sig_tokens = set(t for t in norm.split() if t not in stop_words and len(t) >= 2)
        if msg_sig_tokens and (best_tokens & msg_sig_tokens):
            match_ratio = len(best_tokens & msg_sig_tokens) / len(msg_sig_tokens)
            if match_ratio >= 0.5 or (best_tokens & msg_sig_tokens) == best_tokens:
                logger.info("Found product by token intersection: '%s'", best["name"])
                return best

    return None


def extract_chunk_text(chunk_content: Any) -> str:
    if isinstance(chunk_content, str):
        return chunk_content
    if isinstance(chunk_content, list):
        output = []
        for part in chunk_content:
            if isinstance(part, dict) and "text" in part:
                output.append(part["text"])
            elif isinstance(part, str):
                output.append(part)
        return "".join(output)
    return str(chunk_content) if chunk_content else ""
