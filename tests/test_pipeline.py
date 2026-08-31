import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from database.mongodb import get_mongo_db, check_mongo_health
from services.excel_service import process_procurement_data, process_expenses_data
from services.inventory_service import (
    get_all_products,
    get_product,
    get_low_stock_products,
    ensure_permanent_electronic_inventory,
)
from services.analytics_service import (
    get_inventory_stats,
    get_dashboard_analytics,
)
from services.sync_service import (
    preview_import_deletion,
    delete_import_batch,
    clean_legacy_sample_data,
)

def run_tests():
    print("==================================================")
    print("STEP 1: Checking MongoDB Status & Permanent Electronic Inventory")
    print("==================================================")
    health = check_mongo_health()
    print(json.dumps(health, indent=2))

    seed_res = ensure_permanent_electronic_inventory()
    print("Permanent electronic inventory verified:", seed_res)

    all_prods = get_all_products()
    print(f"Total Master Products in MongoDB: {len(all_prods)}")
    assert len(all_prods) >= 39, f"Expected at least 39 electronic components, got {len(all_prods)}"

    # Verify electronic items
    esp32 = get_product("ESP32-CAM")
    assert esp32 is not None, "ESP32-CAM must exist in permanent inventory"
    assert esp32["source_type"] == "permanent_inventory", "Source type must be permanent_inventory"
    print(f"Verified ESP32-CAM: Stock={esp32['stock']}, Supplier={esp32['supplier']}, Unit Price=Rs.{esp32['unit_price']}")

    arduino = get_product("Arduino Uno R3")
    assert arduino is not None, "Arduino Uno R3 must exist in permanent inventory"
    print(f"Verified Arduino Uno R3: Stock={arduino['stock']}, Supplier={arduino['supplier']}")

    print("\n==================================================")
    print("STEP 2: Testing Chatbot Queries on Electronic Equipment")
    print("==================================================")
    import asyncio
    from services.agent_service import stream_agent_response

    async def test_agent():
        prompts = [
            "How many ESP32-CAM are in stock?",
            "Who supplies SG90 Servo Motor?",
            "Which items are low in stock?",
            "Tell me about HC-SR04 Ultrasonic Sensor",
            "How many nonexistent quantum gadget are in stock?",
        ]
        for prompt in prompts:
            print(f"\n[USER]: {prompt}")
            response_tokens = []
            async for ev in stream_agent_response(prompt, [], None):
                if ev["type"] == "token":
                    response_tokens.append(ev["content"])
                elif ev["type"] == "done":
                    print(f"[ASSISTANT]: {''.join(response_tokens)}")
                    if ev.get("data"):
                        print(f"[DATA PAYLOAD]: {len(ev['data']) if isinstance(ev['data'], list) else 1} item(s) attached")

    asyncio.run(test_agent())

    print("\n==================================================")
    print("STEP 3: Testing Sample Cleanup Mechanism")
    print("==================================================")
    cleanup_res = clean_legacy_sample_data()
    print("Sample cleanup result:", json.dumps(cleanup_res, indent=2))

    post_cleanup_prods = get_all_products()
    print(f"Products after cleanup: {len(post_cleanup_prods)}")
    assert len(post_cleanup_prods) == 39, f"Expected exactly 39 permanent products, got {len(post_cleanup_prods)}"

    print("\n==================================================")
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
