import os
from dotenv import load_dotenv

from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool

from rag_service import retrieve
from inventory_service import (
    get_low_stock_items,
    find_product,
    reorder_product,
)

load_dotenv()

# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are an AI assistant for an IoT hardware inventory management system.

You are friendly, conversational, concise, and helpful.

Use the knowledge base for company/product information.

Use the inventory tools for live stock information.

Never invent inventory quantities.

Answer naturally like ChatGPT.
"""

# ============================================================
# GEMINI
# ============================================================

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.3,
    max_retries=2,
)

# ============================================================
# KNOWLEDGE TOOL
# ============================================================

@tool
def knowledge_base(query: str) -> str:
    """Search the company knowledge base."""

    results = retrieve(query)

    if not results:
        return "No relevant information was found in the knowledge base."

    return "\n\n".join(
        f"Source: {r['source']}\nContent: {r['text']}"
        for r in results
    )

# ============================================================
# INVENTORY TOOLS
# ============================================================

@tool
def inventory_lookup(product_name: str) -> str:
    """Look up live inventory information for a product."""

    product = find_product(product_name)

    if not product:
        return f"{product_name} not found in inventory."

    return (
        f"Product: {product['name']}\n"
        f"Stock: {product['stock']} units\n"
        f"Minimum stock: {product['min_stock']}\n"
        f"Supplier: {product['supplier']}"
    )


@tool
def low_stock_inventory() -> str:
    """Show all low-stock inventory items."""

    items = get_low_stock_items()

    if not items:
        return "No low stock items found."

    return "\n".join(
        f"- {item['name']}: {item['stock']} units"
        for item in items
    )


@tool
def create_reorder(product_name: str) -> str:
    """Create a reorder request for a product."""

    return reorder_product(product_name)

# ============================================================
# AGENT
# ============================================================

agent = None


async def get_agent():
    global agent

    if agent is None:

        all_tools = [
            knowledge_base,
            inventory_lookup,
            low_stock_inventory,
            create_reorder,
        ]

        print("\nLangChain tools loaded:")

        for tool_item in all_tools:
            print(f"- {tool_item.name}")

        agent = create_agent(
            model=llm,
            tools=all_tools,
            system_prompt=SYSTEM_PROMPT,
        )

    return agent

# ============================================================
# ASK AGENT
# ============================================================

async def ask_agent(message: str) -> str:
    current_agent = await get_agent()

    result = await current_agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": message,
                }
            ]
        }
    )

    final_message = result["messages"][-1]
    content = final_message.content

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []

        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    text_parts.append(text)

        if text_parts:
            return "\n".join(text_parts)

    return str(content)

# ============================================================
# COMMAND LINE TEST
# ============================================================

if __name__ == "__main__":

    import asyncio

    async def main():

        print("\nInventory AI Agent")
        print("Type 'exit' to quit.\n")

        while True:

            message = input("You: ").strip()

            if message.lower() == "exit":
                break

            if not message:
                continue

            try:

                answer = await ask_agent(message)

                print(f"\nAssistant: {answer}\n")

            except Exception as error:

                print("\nAgent error:")
                print(repr(error))
                print()

    asyncio.run(main())