import re
import asyncio
import logging
from typing import AsyncGenerator, Optional, List, Dict, Any

# pyrefly: ignore [missing-import]
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from ai.gemini import get_llm
from ai.prompts import SYSTEM_PROMPT
from ai.embeddings import retrieve
from ai.memory import resolve_product_with_context, format_langchain_history
from ai.tools import (
    STOCK_KEYWORDS,
    LOW_STOCK_KEYWORDS,
    REORDER_KEYWORDS,
    SUPPLIER_KEYWORDS,
    EXPENSE_KEYWORDS,
    REQUIREMENT_KEYWORDS,
    ALL_INVENTORY_KEYWORDS,
    has_keyword,
    extract_chunk_text,
)
from services.inventory_service import (
    get_all_products,
    get_product,
    get_low_stock_products,
    create_reorder_request,
)

logger = logging.getLogger("services.agent")


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


async def stream_agent_response(
    message: str,
    conversation_history: List[dict],
    db_session: Any = None,
) -> AsyncGenerator[dict, None]:
    """
    Main entrypoint for WebSocket AI assistant.
    MongoDB is queried as the absolute source of truth.
    """
    lower = message.lower().strip()
    logger.info("User prompt: '%s'", message)

    clean_prompt = re.sub(r"[^\w\s]", "", lower).strip()

    # --------------------------------------------------------
    # 0. GREETINGS & CASUAL CONVERSATION
    # --------------------------------------------------------
    if clean_prompt in ("hi", "hello", "hey", "howdy", "greetings", "good morning", "good afternoon", "good evening", "hi there", "hello there", "hey there"):
        logger.info("Handling Intent: greeting")
        full_msg = "Hello! 👋 How can I help you with your inventory, stock levels, or procurement today?"
        async for ev in _stream_text(full_msg):
            yield ev
        yield {
            "type": "done",
            "message": full_msg,
            "data": [],
            "data_type": "ai",
        }
        return

    if clean_prompt in ("who are you", "what can you do", "what is your role", "help", "who r u", "what do you do"):
        logger.info("Handling Intent: identity/help")
        full_msg = (
            "I am your **Inventory Intelligence Assistant**! 🤖\n\n"
            "I can help you with:\n"
            "• **Stock Checks:** Check live availability and minimum stock levels.\n"
            "• **Stock Alerts:** Identify low-stock items and components needing reorders.\n"
            "• **Suppliers & Vendors:** Look up suppliers, unit prices, and purchase history.\n"
            "• **Procurement & Reorders:** Place automated reorder requests.\n"
            "• **Analytics:** Review spending breakdown and component categories."
        )
        async for ev in _stream_text(full_msg):
            yield ev
        yield {
            "type": "done",
            "message": full_msg,
            "data": [],
            "data_type": "ai",
        }
        return

    # --------------------------------------------------------
    # 1. LOW STOCK INTENT
    # --------------------------------------------------------
    if has_keyword(lower, LOW_STOCK_KEYWORDS):
        logger.info("Handling Intent: low_stock")
        low_items = get_low_stock_products()

        if not low_items:
            full_msg = "✅ Great news! There are currently **no low-stock items**. All inventory levels are healthy!"
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
    if has_keyword(lower, ALL_INVENTORY_KEYWORDS):
        logger.info("Handling Intent: all_inventory")
        items = get_all_products()

        full_msg = f"📦 Here are all **{len(items)} items** currently in inventory."
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
    # 2b. GENERAL REQUIREMENTS INTENT
    # --------------------------------------------------------
    if has_keyword(lower, [
        "what items are required", "what components are required",
        "which items are required", "which components are required",
        "pending requirements", "required items", "required components",
        "what is required", "what are required"
    ]):
        logger.info("Handling Intent: general_requirements")
        all_prods = get_all_products()
        req_prods = [
            p for p in all_prods
            if (p.get("total_qty_required", 0) > 0 or p.get("pending_requirements", 0) > 0)
        ]
        if not req_prods:
            full_msg = "📋 Currently, there are **no active pending requirements** on record."
        else:
            lines = [
                f"- **{p['name']}**: Required: **{p.get('total_qty_required', 0)} units** | Pending: {p.get('pending_requirements', 0)} units | Supplier: **{p.get('supplier')}**"
                for p in req_prods
            ]
            full_msg = (
                f"📋 Found **{len(req_prods)} component(s)** with active requirements:\n\n"
                + "\n".join(lines)
            )
        async for ev in _stream_text(full_msg):
            yield ev
        yield {
            "type": "done",
            "message": full_msg,
            "data": req_prods,
            "data_type": "component",
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
        if has_keyword(lower, REORDER_KEYWORDS):
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
        if has_keyword(lower, SUPPLIER_KEYWORDS):
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
        if has_keyword(lower, EXPENSE_KEYWORDS):
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
        if has_keyword(lower, REQUIREMENT_KEYWORDS):
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
    if has_keyword(lower, STOCK_KEYWORDS + SUPPLIER_KEYWORDS + EXPENSE_KEYWORDS + REORDER_KEYWORDS):
        logger.info("Inventory intent detected but no matching product found.")
        full_msg = (
            "I couldn't find a matching product or component for your query. "
            "Please check the item name and try again, or upload the relevant Excel file to add new inventory data."
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
    messages.extend(format_langchain_history(conversation_history, max_turns=8))
    messages.append(HumanMessage(content=message))

    full_response_text = ""
    try:
        llm = get_llm()
        async for chunk in llm.astream(messages):
            token_text = extract_chunk_text(chunk.content)
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
        "sources": ["master_inventory", "knowledge_base"],
        "mode": "agent",
    }
