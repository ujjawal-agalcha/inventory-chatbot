import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
# pyrefly: ignore [missing-import]
from bson import ObjectId

from database.mongodb import (
    get_products_collection,
    get_procurement_collection,
    get_expenses_collection,
    get_imports_collection,
)
from database.repositories.import_repository import find_import_record_repo
from services.inventory_service import ensure_permanent_electronic_inventory
from services.excel_service import auto_detect_and_import

logger = logging.getLogger("services.sync")


def sync_excel_file_service(
    file_bytes: bytes,
    filename: str,
    uploaded_by: str = "system_sync",
) -> Dict[str, Any]:
    """Live synchronization service for file watchers, webhooks, or cron."""
    return auto_detect_and_import(file_bytes, filename, uploaded_by=uploaded_by)


def preview_import_deletion(batch_or_id: str) -> Dict[str, Any]:
    """
    Preview what records will be deleted or updated before executing deletion.
    """
    import_doc = find_import_record_repo(batch_or_id)
    if not import_doc:
        raise ValueError(f"Import record '{batch_or_id}' not found.")

    imp_id = import_doc["_id"]
    batch_str = str(import_doc.get("import_batch_id", imp_id))
    filename = import_doc.get("filename", "")

    proc_col = get_procurement_collection()
    exp_col = get_expenses_collection()
    prod_col = get_products_collection()

    proc_query = {
        "$or": [
            {"import_id": imp_id},
            {"import_id": batch_str},
            {"import_batch_id": batch_str},
            {"source_file": filename},
        ]
    }
    proc_count = proc_col.count_documents(proc_query)

    exp_query = {
        "$or": [
            {"import_id": imp_id},
            {"import_id": batch_str},
            {"import_batch_id": batch_str},
            {"source_file": filename},
        ]
    }
    exp_count = exp_col.count_documents(exp_query)

    exclusive_prods_query = {
        "source_type": "excel_import",
        "$or": [
            {"created_by_import_id": batch_str},
            {"created_by_import_id": str(imp_id)},
            {"source_files": [filename]},
        ]
    }
    exclusive_prods = list(prod_col.find(exclusive_prods_query))
    exclusive_prod_names = [p.get("name") for p in exclusive_prods]

    shared_prods_query = {
        "$or": [
            {"source_files": filename},
            {"import_batch_ids": batch_str},
        ],
        "_id": {"$nin": [p["_id"] for p in exclusive_prods]}
    }
    shared_prods = list(prod_col.find(shared_prods_query))
    shared_prod_names = [p.get("name") for p in shared_prods]

    return {
        "import_id": str(imp_id),
        "import_batch_id": batch_str,
        "filename": filename,
        "file_type": import_doc.get("file_type", ""),
        "upload_timestamp": str(import_doc.get("upload_timestamp", "")),
        "procurement_records_to_delete": proc_count,
        "expense_records_to_delete": exp_count,
        "products_to_delete_count": len(exclusive_prods),
        "products_to_delete": exclusive_prod_names,
        "products_to_preserve_and_update_count": len(shared_prods),
        "products_to_preserve_and_update": shared_prod_names,
    }


def delete_import_batch(batch_or_id: str) -> Dict[str, Any]:
    """
    Safely delete an import batch:
    - Removes associated procurement and expense records
    - Removes products created exclusively by this import (source_type == 'excel_import')
    - Preserves permanent electronic inventory and updates shared products
    - Removes import history record
    """
    import_doc = find_import_record_repo(batch_or_id)
    if not import_doc:
        raise ValueError(f"Import record '{batch_or_id}' not found.")

    imp_id = import_doc["_id"]
    batch_str = str(import_doc.get("import_batch_id", imp_id))
    filename = import_doc.get("filename", "")

    proc_col = get_procurement_collection()
    exp_col = get_expenses_collection()
    prod_col = get_products_collection()
    imports_col = get_imports_collection()

    proc_del_res = proc_col.delete_many({
        "$or": [
            {"import_id": imp_id},
            {"import_id": batch_str},
            {"import_batch_id": batch_str},
            {"source_file": filename},
        ]
    })

    exp_del_res = exp_col.delete_many({
        "$or": [
            {"import_id": imp_id},
            {"import_id": batch_str},
            {"import_batch_id": batch_str},
            {"source_file": filename},
        ]
    })

    exclusive_prods_query = {
        "source_type": "excel_import",
        "$or": [
            {"created_by_import_id": batch_str},
            {"created_by_import_id": str(imp_id)},
            {"source_files": [filename]},
        ]
    }
    prod_del_res = prod_col.delete_many(exclusive_prods_query)

    remaining_prods = prod_col.find({
        "$or": [
            {"source_files": filename},
            {"import_batch_ids": batch_str},
        ]
    })
    for p in remaining_prods:
        new_sources = [s for s in p.get("source_files", []) if s != filename]
        new_batches = [b for b in p.get("import_batch_ids", []) if str(b) != batch_str]
        
        pid = p["_id"]
        rem_proc = list(proc_col.find({"product_id": pid}))
        rem_exp = list(exp_col.find({"product_id": pid}))

        total_req = sum(r.get("quantity", 0) for r in rem_proc)
        pending_req = sum(r.get("quantity", 0) for r in rem_proc if r.get("order_status", "").lower() in ("pending", "approved"))
        total_exp = sum(e.get("amount", 0.0) for e in rem_exp)

        prod_col.update_one(
            {"_id": pid},
            {
                "$set": {
                    "source_files": new_sources,
                    "import_batch_ids": new_batches,
                    "total_qty_required": total_req,
                    "pending_requirements": pending_req,
                    "total_expense": total_exp,
                    "updated_at": datetime.utcnow(),
                }
            }
        )

    imports_col.delete_one({"_id": imp_id})
    ensure_permanent_electronic_inventory()

    logger.info(
        "Import batch %s (%s) deleted: %d proc records, %d exp records, %d prods removed.",
        batch_str, filename, proc_del_res.deleted_count, exp_del_res.deleted_count, prod_del_res.deleted_count
    )

    return {
        "success": True,
        "import_batch_id": batch_str,
        "filename": filename,
        "deleted_procurement_records": proc_del_res.deleted_count,
        "deleted_expense_records": exp_del_res.deleted_count,
        "deleted_products": prod_del_res.deleted_count,
        "status": "deleted",
    }


def clean_legacy_sample_data() -> Dict[str, Any]:
    """
    Find and safely purge any legacy sample Excel imports and their records.
    Explicitly preserves all legitimate permanent electronic equipment data.
    """
    imports_col = get_imports_collection()
    proc_col = get_procurement_collection()
    exp_col = get_expenses_collection()
    prod_col = get_products_collection()

    sample_filename_patterns = [
        re.compile(r"sample.*\.xlsx?", re.I),
        re.compile(r".*sample.*procurement.*", re.I),
        re.compile(r".*sample.*expense.*", re.I),
    ]

    sample_imports = []
    for imp in imports_col.find({}):
        fn = imp.get("filename", "")
        if any(p.search(fn) for p in sample_filename_patterns) or imp.get("uploaded_by") in ("test_runner", "system_sample"):
            sample_imports.append(imp)

    results = []
    for imp in sample_imports:
        res = delete_import_batch(str(imp["_id"]))
        results.append(res)

    orphan_proc_del = proc_col.delete_many({
        "source_file": {"$regex": "sample", "$options": "i"}
    })
    orphan_exp_del = exp_col.delete_many({
        "source_file": {"$regex": "sample", "$options": "i"}
    })

    sample_prods_del = prod_col.delete_many({
        "source_type": "excel_import",
        "source_files": {"$elemMatch": {"$regex": "sample", "$options": "i"}},
    })

    ensure_permanent_electronic_inventory()

    return {
        "success": True,
        "cleaned_import_batches": results,
        "orphan_procurements_removed": orphan_proc_del.deleted_count,
        "orphan_expenses_removed": orphan_exp_del.deleted_count,
        "sample_products_removed": sample_prods_del.deleted_count,
        "permanent_products_count": prod_col.count_documents({"source_type": "permanent_inventory"}),
    }
