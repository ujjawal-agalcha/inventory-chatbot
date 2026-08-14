import asyncio
from google import genai

from config import GEMINI_API_KEY, GEMINI_MODEL
from rag_service import retrieve
from services.inventory_service import (
    get_component,
    get_low_stock_items,
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
- Use inventory data for stock-related questions.
- Never invent inventory quantities.
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

def inventory_lookup(product_name: str) -> str:
    product = get_component(product_name)

    if not product:
        return f"{product_name} was not found in inventory."

    return (
        f"{product['name']} currently has {product['stock']} units in stock.\n"
        f"Minimum stock level: {product['min_stock']} units.\n"
        f"Supplier: {product['supplier']}."
    )

# ============================================================
# LOW STOCK
# ============================================================

def low_stock_inventory() -> str:
    items = get_low_stock_items()

    if not items:
        return "There are currently no low-stock items."

    return "\n".join(
        f"- {item.name}: {item.stock} units"
        for item in items
    )

# ============================================================
# REORDER
# ============================================================

def create_reorder(product_name: str) -> str:
    success = create_reorder_request(product_name, 25)

    if not success:
        return f"{product_name} was not found in inventory."

    return f"Reorder request created successfully for {product_name} (25 units)."
# ============================================================
# MAIN CHAT FUNCTION
# ============================================================

async def ask_agent(message: str) -> str:
    lower = message.lower()

    # Low stock query
    if "low stock" in lower:
        return low_stock_inventory()

    # Product aliases
    product_aliases = {
        "esp32 cam": "ESP32-CAM",
        "esp32-cam": "ESP32-CAM",
        "esp32 devkit": "ESP32 DevKit V1",
        "esp32 devkit v1": "ESP32 DevKit V1",
        "esp8266": "ESP8266 NodeMCU",
        "nodemcu": "ESP8266 NodeMCU",
        "esp8266 nodemcu": "ESP8266 NodeMCU",
    }

    # Check if any product name is mentioned
    for alias, product in product_aliases.items():
        if alias in lower:
            if "reorder" in lower:
                return create_reorder(product)

            # For any stock-related question
            if any(word in lower for word in [
                "stock", "inventory", "available",
                "quantity", "amount", "units"
            ]):
                return inventory_lookup(product)

    # Knowledge base
    knowledge_context = search_knowledge(message)

    prompt = f"""
{SYSTEM_PROMPT}

Knowledge base:
{knowledge_context}

User: {message}

Answer naturally and conversationally.
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )

    return response.text

    # Knowledge base search
    knowledge_context = search_knowledge(message)

    prompt = f"""
{SYSTEM_PROMPT}

Knowledge base:
{knowledge_context}

User: {message}

Answer naturally and conversationally.
"""

    # Gemini response with fallback
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
                "The AI service is temporarily unavailable due to high demand. "
                "Please try again in a few moments."
            )

# ============================================================
# COMMAND LINE TEST
# ============================================================

if __name__ == "__main__":

    async def main():
        print("Inventory AI Agent")
        print("Type 'exit' to quit.\n")

        while True:
            msg = input("You: ").strip()

            if msg.lower() == "exit":
                break

            answer = await ask_agent(msg)
            print(f"\nAssistant: {answer}\n")

    asyncio.run(main())