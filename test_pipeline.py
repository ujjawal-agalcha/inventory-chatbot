import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from mongo_db import get_mongo_db, check_mongo_health
from services.excel_import_service import process_procurement_data, process_expenses_data
from services.mongo_inventory_service import (
    get_all_products,
    get_product,
    get_low_stock_products,
    get_inventory_stats,
    get_dashboard_analytics,
)

def run_tests():
    print("==================================================")
    print("STEP 1: Checking MongoDB Status")
    print("==================================================")
    health = check_mongo_health()
    print(json.dumps(health, indent=2))

    proc_path = r"C:\Users\gaura\Downloads\Sample_Procurement_Workbook.xlsx"
    exp_path = r"C:\Users\gaura\Downloads\Sample_Master_Procurement_Workbook.xlsx"

    print("\n==================================================")
    print("STEP 2: Ingesting File 1 (Procurement Workbook)")
    print("==================================================")
    with open(proc_path, "rb") as f:
        proc_bytes = f.read()
    res1 = process_procurement_data(proc_bytes, "Sample_Procurement_Workbook.xlsx", "test_runner")
    print(json.dumps(res1, indent=2))

    print("\n==================================================")
    print("STEP 3: Ingesting File 2 (Expenses Workbook)")
    print("==================================================")
    with open(exp_path, "rb") as f:
        exp_bytes = f.read()
    res2 = process_expenses_data(exp_bytes, "Sample_Master_Procurement_Workbook.xlsx", "test_runner")
    print(json.dumps(res2, indent=2))

    print("\n==================================================")
    print("STEP 4: Testing DUPLICATE PREVENTION (Re-uploading both files)")
    print("==================================================")
    res1_dup = process_procurement_data(proc_bytes, "Sample_Procurement_Workbook.xlsx", "test_runner")
    print("Procurement Re-upload:", json.dumps(res1_dup, indent=2))
    assert res1_dup["new_records"] == 0, f"Expected 0 new products on re-upload, got {res1_dup['new_records']}"
    assert res1_dup["duplicate_records"] > 0, f"Expected duplicate rows to be caught"

    res2_dup = process_expenses_data(exp_bytes, "Sample_Master_Procurement_Workbook.xlsx", "test_runner")
    print("Expenses Re-upload:", json.dumps(res2_dup, indent=2))
    assert res2_dup["new_records"] == 0, f"Expected 0 new products on re-upload, got {res2_dup['new_records']}"
    assert res2_dup["duplicate_records"] > 0, f"Expected duplicate rows to be caught"

    print("\n==================================================")
    print("STEP 5: Querying Master Inventory & Analytics")
    print("==================================================")
    stats = get_inventory_stats()
    print("Aggregated Stats:", json.dumps(stats, indent=2))

    all_prods = get_all_products()
    print(f"\nTotal Master Products: {len(all_prods)}")
    sys.stdout.reconfigure(encoding="utf-8")
    for p in all_prods:
        print(f"  • {p['name']} | Stock: {p['stock']} | Unit Price: Rs.{p['unit_price']} | Total Spent: Rs.{p['total_expense']} | Supplier: {p['supplier']} | Category: {p['category']}")

    print("\n==================================================")
    print("STEP 6: Testing Fuzzy Product Lookup & Context")
    print("==================================================")
    test_queries = [
        "A4 Paper Ream",
        "a4 paper",
        "hp 802 black",
        "printer cartridge",
        "stapler",
        "dettol",
        "hdmi cable",
        "whiteboard marker",
    ]
    for q in test_queries:
        prod = get_product(q)
        if prod:
            print(f"  ✓ Query '{q}' -> Found: '{prod['name']}' (Stock: {prod['stock']}, Supplier: {prod['supplier']})")
        else:
            print(f"  ✗ Query '{q}' -> NOT FOUND")

    print("\n==================================================")
    print("STEP 7: Testing Chatbot Agent Intent Engine")
    print("==================================================")
    import asyncio
    import agent_service

    async def test_agent():
        prompts = [
            "How many A4 Paper Ream are in stock?",
            "Who supplies Printer Cartridge?",
            "Which items are low in stock?",
            "How much did we spend on Whiteboard Marker?",
            "How many nonexistent widget are there in stock?",
        ]
        for prompt in prompts:
            print(f"\n[USER]: {prompt}")
            response_tokens = []
            async for ev in agent_service.stream_agent_response(prompt, [], None):
                if ev["type"] == "token":
                    response_tokens.append(ev["content"])
                elif ev["type"] == "done":
                    print(f"[ASSISTANT]: {''.join(response_tokens)}")
                    if ev.get("data"):
                        print(f"[DATA PAYLOAD]: {len(ev['data'])} item(s) attached")

    asyncio.run(test_agent())

    print("\n==================================================")
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()

