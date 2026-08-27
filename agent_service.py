import logging
import re
import asyncio
from typing import AsyncGenerator, Optional, List, Dict, Any

# pyrefly: ignore [missing-import]
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from config import GEMINI_API_KEY, GEMINI_MODEL
from rag_service import retrieve

from services.mongo_inventory_service import (
    get_all_products,
    get_product,
    get_low_stock_products,
    search_products,
    create_reorder_request,
    get_inventory_stats,
)
from services.excel_import_service import normalize_text

logger = logging.getLogger("agent")

# ============================================================
# GEMINI CLIENT
# ============================================================

def get_llm():
    """Create the LangChain Gemini client."""
    clean_model = (
        GEMINI_MODEL.replace("models/", "")
        if GEMINI_MODEL
        else "gemini-3.5-flash"
    )
    return ChatGoogleGenerativeAI(
        model=clean_model,
        google_api_key=GEMINI_API_KEY,
        temperature=0.2,
    )


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are an intelligent AI Assistant for a Real Inventory Management & Procurement System.

CRITICAL INVENTORY RULES:
1. Never invent or hallucinate inventory data, stock quantities, suppliers, prices, or expense figures.
2. The MongoDB database is the absolute single source of truth.
3. If a product or component is not found in the database, clearly and explicitly state that it does not exist in the inventory records.
4. For technical, functional, or policy questions not answered by live stock counts, refer to the provided knowledge base context.
5. Always format numbers, currencies (₹ / $), and item names cleanly.
"""


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def _normalize_text(text: str) -> str:
    return normalize_text(text)


# ============================================================
# PRODUCT DETECTION (DYNAMIC VIA MONGODB)
# ============================================================

def detect_product(message: str) -> Optional[dict]:
    """
    Resolve a product from the user's natural-language message using MongoDB.
    1. Direct match with get_product(message)
    2. Substring & alias matching against all products in MongoDB
    3. Token-based intelligent search
    """
    if not message:
        return None

    norm = _normalize_text(message)
    if not norm:
        return None

    # 1. Direct lookup
    direct = get_product(message)
    if direct:
        logger.info("Direct MongoDB product match: '%s'", direct["name"])
        return direct

    # 2. Check all products in MongoDB for alias or substring match
    all_items = get_all_products()
    
    # Sort items by name length descending so specific names match before generic words
    sorted_items = sorted(all_items, key=lambda x: len(x.get("name", "")), reverse=True)

    for item in sorted_items:
        item_norm = item.get("normalized_name", "")
        item_name_lower = item.get("name", "").lower()

        # Check if product name is inside user query
        if item_norm and item_norm in norm:
            logger.info("Found product by normalized name in query: '%s'", item["name"])
            return item

        if item_name_lower and item_name_lower in message.lower():
            logger.info("Found product by name substring in query: '%s'", item["name"])
            return item

        # Check aliases
        for alias in item.get("aliases", []):
            alias_norm = _normalize_text(alias)
            if alias_norm and alias_norm in norm:
                logger.info("Found product by alias in query: '%s' -> '%s'", alias, item["name"])
                return item

    # 3. Intelligent search via MongoDB
    search_results = search_products(message, limit=3)
    if search_results:
        best = search_results[0]
        # Verify confidence with significant tokens
        best_norm = best.get("normalized_name", "")
        best_tokens = set(best_norm.split())
        stop_words = {
            "how", "many", "much", "is", "are", "there", "in", "stock", "available",
            "do", "we", "have", "got", "the", "a", "an", "what", "which", "please",
            "tell", "me", "about", "show", "give", "current", "units", "left", "who", "supplies"
        }
        msg_sig_tokens = set(t for t in norm.split() if t not in stop_words and len(t) >= 2)
        if msg_sig_tokens and (best_tokens & msg_sig_tokens):
            match_ratio = len(best_tokens & msg_sig_tokens) / len(msg_sig_tokens)
            if match_ratio >= 0.5 or (best_tokens & msg_sig_tokens) == best_tokens:
                logger.info("Found product by token intersection: '%s'", best["name"])
                return best

    return None


# ============================================================
# CONTEXTUAL PRODUCT RESOLUTION (MULTI-TURN MEMORY)
# ============================================================

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


def _has_keyword(text: str, keywords: List[str]) -> bool:
    lower = text.lower()
    return any(k in lower for k in keywords)


# ============================================================
# STREAM HELPER
# ============================================================

async def _stream_text(text: str) -> AsyncGenerator[dict, None]:
    """Stream text tokens smoothly."""
    words = text.split(" ")
    for index, word in enumerate(words):
        content = word
        if index < len(words) - 1:
            content += " "
        yield {
            "type": "token",
            "content": content,
        }
        await asyncio.sleep(0.015)


def _extract_chunk_text(chunk_content: Any) -> str:
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


# ============================================================
# MAIN AGENT STREAMING DISPATCHER (MONGODB POWERED)
# ============================================================

async def stream_agent_response(
    message: str,
    conversation_history: List[dict],
    db_session: Any = None,  # SQLite session for auth/history if passed
) -> AsyncGenerator[dict, None]:
    """
    Main entrypoint for WebSocket AI assistant.
    MongoDB is queried as the absolute source of truth.
    """
    lower = message.lower().strip()
    logger.info("User prompt: '%s'", message)

    # --------------------------------------------------------
    # 1. LOW STOCK INTENT
    # --------------------------------------------------------
    if _has_keyword(lower, LOW_STOCK_KEYWORDS):
        logger.info("Handling Intent: low_stock")
        low_items = get_low_stock_products()

        if not low_items:
            full_msg = "✅ There are currently **no low-stock items** in the database. All inventory levels are healthy!"
            async for ev in _stream_text(full_msg):
                yield ev
            yield {
                "type": "done",
                "message": full_msg,
                "data": [],
                "data_type": "low_stock",
            }
            return

        lines = []
        for item in low_items:
            status_tag = "🔴 Out of Stock" if item["stock"] == 0 else f"⚠️ Low Stock ({item['stock']} units)"
            lines.append(
                f"- **{item['name']}**: {status_tag} | Minimum: {item['min_stock']} units | Supplier: **{item['supplier']}**"
            )

        full_msg = (
            f"The following **{len(low_items)} item(s)** are currently at or below minimum stock level:\n\n"
            + "\n".join(lines)
        )

        async for ev in _stream_text(full_msg):
            yield ev

        yield {
            "type": "done",
            "message": full_msg,
            "data": low_items,
            "data_type": "low_stock",
        }
        return

    # --------------------------------------------------------
    # 2. ALL INVENTORY / LIST INTENT
    # --------------------------------------------------------
    if _has_keyword(lower, ALL_INVENTORY_KEYWORDS):
        logger.info("Handling Intent: all_inventory")
        items = get_all_products()

        full_msg = f"📦 Showing all **{len(items)} items** registered in the MongoDB Master Inventory dataset."
        async for ev in _stream_text(full_msg):
            yield ev

        yield {
            "type": "done",
            "message": full_msg,
            "data": items,
            "data_type": "inventory",
        }
        return

    # --------------------------------------------------------
    # 3. CONTEXTUAL PRODUCT RESOLUTION
    # --------------------------------------------------------
    product = resolve_product_with_context(message, conversation_history)
    logger.info("Resolved product: %s", product["name"] if product else "None")

    # --------------------------------------------------------
    # 4. PRODUCT-SPECIFIC INVENTORY QUERIES
    # --------------------------------------------------------
    if product:
        name = product["name"]
        stock = product["stock"]
        min_stock = product["min_stock"]
        supplier = product["supplier"]
        category = product["category"]
        unit_price = product.get("unit_price", 0.0)
        total_exp = product.get("total_expense", 0.0)
        req_qty = product.get("total_qty_required", 0)
        pending_req = product.get("pending_requirements", 0)
        status_str = "⚠️ Low Stock" if stock <= min_stock else ("🔴 Out of Stock" if stock == 0 else "✅ In Stock")

        # 4a. REORDER
        if _has_keyword(lower, REORDER_KEYWORDS):
            logger.info("Handling Intent: reorder for '%s'", name)
            reorder_qty = max(min_stock - stock, 10)
            reorder_record = create_reorder_request(
                item_identifier=name,
                quantity=reorder_qty,
                vendor=supplier,
                remarks="Automated reorder triggered via Chatbot",
            )

            if reorder_record:
                full_msg = (
                    f"📦 **Reorder Request Created Successfully** for **{name}**!\n\n"
                    f"- **Quantity Ordered:** {reorder_qty} units\n"
                    f"- **Supplier / Vendor:** {supplier}\n"
                    f"- **Estimated Amount:** ₹{reorder_qty * unit_price:,.2f}\n"
                    f"- **Status:** Pending Approval"
                )
            else:
                full_msg = f"Could not create reorder request for **{name}**."

            async for ev in _stream_text(full_msg):
                yield ev

            yield {
                "type": "done",
                "message": full_msg,
                "data": product,
                "data_type": "reorder",
            }
            return

        # 4b. SUPPLIER / VENDOR
        if _has_keyword(lower, SUPPLIER_KEYWORDS):
            logger.info("Handling Intent: supplier for '%s'", name)
            full_msg = (
                f"🚚 **{name}** is supplied by **{supplier}**.\n\n"
                f"- **Market / Source:** {product.get('market', 'Direct')}\n"
                f"- **Unit Price:** ₹{unit_price:,.2f}\n"
                f"- **Current Stock:** {stock} units"
            )
            async for ev in _stream_text(full_msg):
                yield ev
            yield {
                "type": "done",
                "message": full_msg,
                "data": product,
                "data_type": "component",
            }
            return

        # 4c. EXPENSE / SPENDING
        if _has_keyword(lower, EXPENSE_KEYWORDS):
            logger.info("Handling Intent: expense for '%s'", name)
            full_msg = (
                f"💰 **Expense Details for {name}:**\n\n"
                f"- **Total Amount Spent:** ₹{total_exp:,.2f}\n"
                f"- **Total Units Purchased:** {product.get('total_qty_purchased', 0)} units\n"
                f"- **Unit Price:** ₹{unit_price:,.2f}\n"
                f"- **Current Stock on Hand:** {stock} units"
            )
            async for ev in _stream_text(full_msg):
                yield ev
            yield {
                "type": "done",
                "message": full_msg,
                "data": product,
                "data_type": "component",
            }
            return

        # 4d. REQUIREMENTS / PROCUREMENT
        if _has_keyword(lower, REQUIREMENT_KEYWORDS):
            logger.info("Handling Intent: requirements for '%s'", name)
            full_msg = (
                f"📋 **Procurement & Requirements for {name}:**\n\n"
                f"- **Total Required Quantity:** {req_qty} units\n"
                f"- **Pending Orders / Approvals:** {pending_req} units\n"
                f"- **Current Stock Available:** {stock} units\n"
                f"- **Supplier:** {supplier}"
            )
            async for ev in _stream_text(full_msg):
                yield ev
            yield {
                "type": "done",
                "message": full_msg,
                "data": product,
                "data_type": "component",
            }
            return

        # 4e. STOCK / GENERAL PRODUCT LOOKUP
        logger.info("Handling Intent: stock lookup for '%s'", name)
        full_msg = (
            f"**{name}**\n\n"
            f"- **Current Stock:** **{stock} units** ({status_str})\n"
            f"- **Minimum Stock Level:** {min_stock} units\n"
            f"- **Category:** {category}\n"
            f"- **Supplier / Vendor:** {supplier}\n"
            f"- **Unit Price:** ₹{unit_price:,.2f}"
        )
        if product.get("details"):
            full_msg += f"\n- **Details / Specs:** {product['details']}"

        async for ev in _stream_text(full_msg):
            yield ev

        yield {
            "type": "done",
            "message": full_msg,
            "data": [product],
            "data_type": "component",
        }
        return

    # --------------------------------------------------------
    # 5. INVENTORY QUESTION BUT PRODUCT NOT FOUND
    # --------------------------------------------------------
    if _has_keyword(lower, STOCK_KEYWORDS + SUPPLIER_KEYWORDS + EXPENSE_KEYWORDS + REORDER_KEYWORDS):
        logger.info("Inventory intent detected but no matching product found in MongoDB.")
        full_msg = (
            "I searched the live MongoDB database but could not find a matching product or component "
            "for your query. Please verify the item name or upload the relevant Excel workbook."
        )
        async for ev in _stream_text(full_msg):
            yield ev
        yield {
            "type": "done",
            "message": full_msg,
            "data": [],
            "data_type": "inventory",
        }
        return

    # --------------------------------------------------------
    # 6. RAG / GEMINI AI KNOWLEDGE FALLBACK
    # --------------------------------------------------------
    logger.info("Dispatching to Gemini LLM with RAG Knowledge Context")
    knowledge_results = retrieve(message)
    knowledge_context = ""
    if knowledge_results:
        knowledge_context = "\n\n".join([
            f"Source ({r['source']}): {r['text']}" for r in knowledge_results
        ])

    messages = [
        SystemMessage(content=SYSTEM_PROMPT)
    ]
    if knowledge_context:
        messages.append(
            SystemMessage(content=f"Relevant Knowledge Base Information:\n{knowledge_context}")
        )

    # Append conversation memory
    if conversation_history:
        for turn in conversation_history[-8:]:
            role = turn.get("role")
            content = turn.get("content", "")
            if not content:
                continue
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=message))

    full_response_text = ""
    try:
        llm = get_llm()
        async for chunk in llm.astream(messages):
            token_text = _extract_chunk_text(chunk.content)
            if token_text:
                full_response_text += token_text
                yield {
                    "type": "token",
                    "content": token_text,
                }
    except Exception as exc:
        logger.exception("Gemini streaming error: %s", exc)
        full_response_text = "I encountered an error communicating with the AI model. Please try again."
        yield {
            "type": "token",
            "content": full_response_text,
        }

    yield {
        "type": "done",
        "message": full_response_text,
        "data": [],
        "data_type": "ai",
    }


# ============================================================
# COMPATIBILITY WRAPPER
# ============================================================

async def ask_agent(
    message: str,
    db: Any = None,
    conversation_history: Optional[List[dict]] = None,
) -> dict:
    """Synchronous-like wrapper for non-WebSocket callers."""
    history = conversation_history or []
    full_text = ""
    final_data = []
    final_type = "ai"

    async for event in stream_agent_response(message, history, db):
        if event["type"] == "done":
            full_text = event.get("message", "")
            final_data = event.get("data", [])
            final_type = event.get("data_type", "ai")

    return {
        "type": final_type,
        "message": full_text,
        "answer": full_text,
        "data": final_data,
        "sources": ["live_mongodb_inventory", "knowledge_base"],
        "mode": "agent",
    }