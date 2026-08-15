from google import genai
from sqlalchemy.orm import Session

from config import GEMINI_API_KEY, GEMINI_MODEL
from rag_service import retrieve

from services.inventory_service import (
    get_all_inventory,
    get_component,
    get_low_stock_items,
    search_inventory,
    create_reorder_request,
)


# ============================================================
# GEMINI CLIENT
# ============================================================

client = genai.Client(api_key=GEMINI_API_KEY)


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are an AI assistant for an IoT hardware inventory management system.

You are friendly, conversational, concise, and helpful.

Rules:

- Answer naturally like ChatGPT.
- Use the knowledge base for company/product information.
- Use live inventory data for stock-related questions.
- Never invent inventory quantities.
- When live inventory data is provided, trust it over the knowledge base.
- If inventory information is unavailable, clearly say so.
"""


# ============================================================
# KNOWLEDGE SEARCH
# ============================================================

def search_knowledge(query: str) -> str:
    results = retrieve(query)

    if not results:
        return "No relevant information found in the knowledge base."

    return "\n\n".join(
        f"Source: {r['source']}\n{r['text']}"
        for r in results
    )


# ============================================================
# INVENTORY LOOKUP
# ============================================================

def inventory_lookup(product_name: str, db: Session) -> str:

    product = get_component(db, product_name)

    if not product:
        return f"{product_name} was not found in inventory."

    return (
        f"{product.name} currently has {product.stock} units in stock.\n"
        f"Minimum stock level: {product.min_stock} units.\n"
        f"Supplier: {product.supplier}."
    )


# ============================================================
# LOW STOCK
# ============================================================

def low_stock_inventory(db: Session) -> str:

    items = get_low_stock_items(db)

    if not items:
        return "There are currently no low-stock items."

    return "\n".join(
        f"- {item.name}: {item.stock} units"
        for item in items
    )


# ============================================================
# INVENTORY SEARCH
# ============================================================

def inventory_search(message: str, db: Session) -> str:

    items = search_inventory(db, message)

    if not items:
        return "No matching inventory items were found."

    return "\n".join(
        f"- {item.name}: {item.stock} units "
        f"(minimum {item.min_stock}, supplier: {item.supplier})"
        for item in items[:10]
    )


# ============================================================
# REORDER
# ============================================================

def create_reorder(product_name: str, db: Session) -> str:

    product = get_component(db, product_name)

    if not product:
        return f"{product_name} was not found in inventory."

    try:
        result = create_reorder_request(
            db=db,
            item_id=product.id,
            quantity=25,
        )

        if not result:
            return f"Could not create reorder request for {product_name}."

        return (
            f"Reorder request created successfully for "
            f"{product.name} (25 units)."
        )

    except Exception as e:
        print(f"Reorder error: {e}")
        return "Unable to create the reorder request."


# ============================================================
# PRODUCT ALIASES
# ============================================================

PRODUCT_ALIASES = {
    "esp32 cam": "ESP32-CAM",
    "esp32-cam": "ESP32-CAM",
    "esp32 devkit": "ESP32 DevKit V1",
    "esp32 devkit v1": "ESP32 DevKit V1",
    "esp8266": "ESP8266 NodeMCU",
    "nodemcu": "ESP8266 NodeMCU",
    "esp8266 nodemcu": "ESP8266 NodeMCU",
}


# ============================================================
# MAIN CHAT FUNCTION
# ============================================================

async def ask_agent(message: str, db: Session) -> str:

    lower = message.lower().strip()

    # --------------------------------------------------------
    # LOW STOCK
    # --------------------------------------------------------

    if any(x in lower for x in [
        "low stock",
        "low-stock",
        "shortage",
    ]):
        return low_stock_inventory(db)


    # --------------------------------------------------------
    # ALL INVENTORY
    # --------------------------------------------------------

    if any(x in lower for x in [
        "all inventory",
        "all products",
        "all components",
        "show inventory",
        "show everything",
    ]):
        items = get_all_inventory(db)

        if not items:
            return "There are currently no inventory items."

        return "\n".join(
            f"- {item.name}: {item.stock} units"
            for item in items
        )


    # --------------------------------------------------------
    # PRODUCT ALIASES
    # --------------------------------------------------------

    for alias, product_name in PRODUCT_ALIASES.items():

        if alias in lower:

            if "reorder" in lower:
                return create_reorder(product_name, db)

            if any(word in lower for word in [
                "stock",
                "inventory",
                "available",
                "quantity",
                "amount",
                "units",
                "how many",
            ]):
                return inventory_lookup(product_name, db)


    # --------------------------------------------------------
    # EXACT PRODUCT NAME MATCH
    # --------------------------------------------------------

    all_items = get_all_inventory(db)

    for item in all_items:

        if item.name.lower() in lower:

            if "reorder" in lower:
                return create_reorder(item.name, db)

            if any(word in lower for word in [
                "stock",
                "inventory",
                "available",
                "quantity",
                "amount",
                "units",
                "how many",
            ]):
                return inventory_lookup(item.name, db)


    # --------------------------------------------------------
    # GENERAL INVENTORY SEARCH
    # --------------------------------------------------------

    if any(word in lower for word in [
        "inventory",
        "stock",
        "available",
        "availability",
        "quantity",
        "units",
        "warehouse",
    ]):

        result = inventory_search(message, db)

        if result != "No matching inventory items were found.":
            return result


    # --------------------------------------------------------
    # KNOWLEDGE BASE
    # --------------------------------------------------------

    knowledge_context = search_knowledge(message)

    prompt = f"""
{SYSTEM_PROMPT}

Knowledge base:
{knowledge_context}

User: {message}

Answer naturally and conversationally.
"""

    try:

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )

        return response.text

    except Exception as e:

        print(f"Gemini primary model failed: {e}")

        try:

            response = client.models.generate_content(
                model="models/gemini-2.5-flash-lite",
                contents=prompt,
            )

            return response.text

        except Exception as e2:

            print(f"Gemini fallback failed: {e2}")

            return (
                "The AI service is temporarily unavailable. "
                "Please try again in a few moments."
            )


# ============================================================
# COMMAND LINE TEST
# ============================================================

if __name__ == "__main__":

    from models import SessionLocal

    async def main():

        db = SessionLocal()

        try:

            print("Inventory AI Agent")
            print("Type 'exit' to quit.\n")

            while True:

                msg = input("You: ").strip()

                if msg.lower() == "exit":
                    break

                answer = await ask_agent(msg, db)

                print(f"\nAssistant: {answer}\n")

        finally:
            db.close()


    import asyncio
    asyncio.run(main())