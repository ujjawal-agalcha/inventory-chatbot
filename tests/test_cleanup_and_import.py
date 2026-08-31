import os
import sys
import io
import json
import openpyxl
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from database.mongodb import get_mongo_db, check_mongo_health
from services.excel_service import (
    process_procurement_data,
    process_expenses_data,
)
from services.inventory_service import (
    get_all_products,
    get_product,
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

def create_sample_excel_procurement_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Procurement"
    ws.append(["S No", "Name", "Details", "Qty", "Unit Price", "Amount", "Order Date", "Status", "Vendor", "Approved By", "Remarks"])
    ws.append([1, "Sample Whiteboard Marker", "Black bullet tip", 20, 25.0, 500.0, "2026-08-01", "Fulfilled", "Office Supplies Co", "Manager", "Sample office order"])
    ws.append([2, "Sample A4 Paper Ream", "75 GSM 500 sheets", 10, 280.0, 2800.0, "2026-08-02", "Pending", "Paper World", "Admin", "Sample paper order"])
    ws.append([3, "ESP32-CAM", "Additional camera modules", 5, 550.0, 2750.0, "2026-08-03", "Fulfilled", "Tech Components Pvt. Ltd.", "Lead", "Restock ESP32-CAM"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

def create_sample_excel_expenses_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "August Expenses"
    ws.append(["S No", "Component", "Quantity", "Unit Price", "Amount", "Date", "Status", "Remark"])
    ws.append([1, "Sample Stapler Heavy Duty", 4, 150.0, 600.0, "2026-08-05", "Paid", "Office stationery expense"])
    ws.append([2, "Sample Dettol Soap Pack", 6, 45.0, 270.0, "2026-08-06", "Paid", "Hygiene supplies"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

def run_comprehensive_test():
    print("==================================================")
    print("1. Baseline: Verifying Permanent Electronic Inventory")
    print("==================================================")
    ensure_permanent_electronic_inventory()
    baseline_prods = get_all_products()
    print(f"Baseline permanent products count: {len(baseline_prods)}")
    assert len(baseline_prods) == 39, f"Expected 39 items, got {len(baseline_prods)}"

    print("\n==================================================")
    print("2. Simulating User Upload of Sample Procurement Sheet")
    print("==================================================")
    proc_bytes = create_sample_excel_procurement_bytes()
    proc_res = process_procurement_data(proc_bytes, "Sample_Procurement_Workbook.xlsx", "tester")
    print("Procurement Ingest Result:", json.dumps(proc_res, indent=2))
    assert proc_res["new_records"] == 2, "Expected 2 new products (Marker, Paper) and 1 updated (ESP32-CAM)"
    assert proc_res["updated_records"] == 1, "Expected ESP32-CAM to be updated"

    print("\n==================================================")
    print("3. Simulating User Upload of Sample Expenses Sheet")
    print("==================================================")
    exp_bytes = create_sample_excel_expenses_bytes()
    exp_res = process_expenses_data(exp_bytes, "Sample_Master_Procurement_Workbook.xlsx", "tester")
    print("Expenses Ingest Result:", json.dumps(exp_res, indent=2))
    assert exp_res["new_records"] == 2, "Expected 2 new products (Stapler, Soap)"

    total_with_samples = get_all_products()
    print(f"Total products with sample imports: {len(total_with_samples)} (39 electronic + 4 sample)")
    assert len(total_with_samples) == 43, f"Expected 43 products, got {len(total_with_samples)}"

    print("\n==================================================")
    print("4. Testing Duplicate Prevention (Re-uploading same sheets)")
    print("==================================================")
    proc_dup_res = process_procurement_data(proc_bytes, "Sample_Procurement_Workbook.xlsx", "tester")
    print("Procurement Re-upload Result:", json.dumps(proc_dup_res, indent=2))
    assert proc_dup_res["new_records"] == 0, "Expected 0 new records on re-upload"
    assert proc_dup_res["duplicate_records"] == 3, f"Expected 3 duplicate rows skipped, got {proc_dup_res['duplicate_records']}"

    exp_dup_res = process_expenses_data(exp_bytes, "Sample_Master_Procurement_Workbook.xlsx", "tester")
    print("Expenses Re-upload Result:", json.dumps(exp_dup_res, indent=2))
    assert exp_dup_res["new_records"] == 0, "Expected 0 new records on re-upload"
    assert exp_dup_res["duplicate_records"] == 2, f"Expected 2 duplicate rows skipped, got {exp_dup_res['duplicate_records']}"

    print("\n==================================================")
    print("5. Testing Preview of Import Deletion")
    print("==================================================")
    prev = preview_import_deletion(proc_res["import_batch_id"])
    print("Deletion Preview:", json.dumps(prev, indent=2))
    assert prev["products_to_delete_count"] == 2, "Expected 2 sample products to be deleted"
    assert prev["products_to_preserve_and_update_count"] >= 1, "Expected ESP32-CAM to be preserved"

    print("\n==================================================")
    print("6. Executing Clean Sample Data Purge")
    print("==================================================")
    cleanup_result = clean_legacy_sample_data()
    print("Cleanup Result:", json.dumps(cleanup_result, indent=2))

    post_cleanup_prods = get_all_products()
    print(f"Total products after cleanup: {len(post_cleanup_prods)}")
    assert len(post_cleanup_prods) == 39, f"Expected exactly 39 products, got {len(post_cleanup_prods)}"

    # Ensure no sample items remain
    assert get_product("Sample Whiteboard Marker") is None, "Sample Whiteboard Marker must be deleted"
    assert get_product("Sample A4 Paper Ream") is None, "Sample A4 Paper Ream must be deleted"
    assert get_product("Sample Stapler Heavy Duty") is None, "Sample Stapler Heavy Duty must be deleted"
    assert get_product("Sample Dettol Soap Pack") is None, "Sample Dettol Soap Pack must be deleted"

    # Ensure permanent electronic items are 100% intact
    esp32 = get_product("ESP32-CAM")
    assert esp32 is not None, "ESP32-CAM must be intact"
    assert esp32["source_type"] == "permanent_inventory"
    print(f"ESP32-CAM Verified: Stock={esp32['stock']}, Supplier={esp32['supplier']}")

    arduino = get_product("Arduino Uno R3")
    assert arduino is not None, "Arduino Uno R3 must be intact"
    print(f"Arduino Uno R3 Verified: Stock={arduino['stock']}, Supplier={arduino['supplier']}")

    print("\n==================================================")
    print("7. Verifying Analytics and Dashboard Data")
    print("==================================================")
    analytics = get_dashboard_analytics()
    print(f"Analytics Categories: {len(analytics['categories'])}")
    print(f"Analytics Suppliers: {len(analytics['suppliers'])}")
    print("Stats:", json.dumps(analytics["stats"], indent=2))
    assert analytics["stats"]["total_components"] == 39

    print("\n==================================================")
    print("ALL COMPREHENSIVE IMPORT & CLEANUP TESTS PASSED!")
    print("==================================================")

if __name__ == "__main__":
    run_comprehensive_test()
