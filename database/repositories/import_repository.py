import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
# pyrefly: ignore [missing-import]
from bson import ObjectId

from database.mongodb import (
    get_imports_collection,
    get_procurement_collection,
    get_expenses_collection,
)

logger = logging.getLogger("database.repositories.import")


def _import_doc_to_dict(doc: dict) -> dict:
    if not doc:
        return {}
    return {
        "id": str(doc.get("_id", "")),
        "import_batch_id": str(doc.get("import_batch_id", doc.get("_id", ""))),
        "filename": doc.get("filename", ""),
        "file_type": doc.get("file_type", ""),
        "source_type": doc.get("source_type", "excel_import"),
        "upload_timestamp": (
            doc["upload_timestamp"].isoformat()
            if isinstance(doc.get("upload_timestamp"), datetime)
            else str(doc.get("upload_timestamp", ""))
        ),
        "uploaded_by": doc.get("uploaded_by", ""),
        "total_rows": doc.get("total_rows", 0),
        "valid_records": doc.get("valid_records", 0),
        "new_records": doc.get("new_records", 0),
        "updated_records": doc.get("updated_records", 0),
        "duplicate_records": doc.get("duplicate_records", 0),
        "rejected_records": doc.get("rejected_records", 0),
        "errors": doc.get("errors", []),
        "status": doc.get("status", "completed"),
    }


def _procurement_doc_to_dict(doc: dict) -> dict:
    if not doc:
        return {}
    return {
        "id": str(doc.get("_id", "")),
        "product_id": str(doc.get("product_id", "")),
        "product_name": doc.get("product_name", ""),
        "details": doc.get("details", ""),
        "quantity": doc.get("quantity", 0),
        "unit_price": doc.get("unit_price", 0.0),
        "amount": doc.get("amount", 0.0),
        "market": doc.get("market", ""),
        "order_date": doc.get("order_date_str", ""),
        "order_status": doc.get("order_status", "Pending"),
        "vendor_name": doc.get("vendor_name", ""),
        "supplier": doc.get("vendor_name", ""),
        "approved_by": doc.get("approved_by", ""),
        "remarks": doc.get("remarks", ""),
        "requirement_issued_by": doc.get("requirement_issued_by", ""),
        "url": doc.get("url", ""),
        "source_type": doc.get("source_type", "excel_import"),
        "import_id": str(doc.get("import_id", "")),
        "import_batch_id": str(doc.get("import_batch_id", doc.get("import_id", ""))),
        "source_file": doc.get("source_file", ""),
    }


def _expense_doc_to_dict(doc: dict) -> dict:
    if not doc:
        return {}
    return {
        "id": str(doc.get("_id", "")),
        "product_id": str(doc.get("product_id", "")),
        "product_name": doc.get("product_name", ""),
        "quantity": doc.get("quantity", 0),
        "unit_price": doc.get("unit_price", 0.0),
        "amount": doc.get("amount", 0.0),
        "date": doc.get("date_str", ""),
        "status": doc.get("status", "Paid"),
        "remark": doc.get("remark", ""),
        "expense_month": doc.get("expense_month", ""),
        "source_type": doc.get("source_type", "excel_import"),
        "import_id": str(doc.get("import_id", "")),
        "import_batch_id": str(doc.get("import_batch_id", doc.get("import_id", ""))),
        "source_file": doc.get("source_file", ""),
    }


def create_import_record_repo(import_doc: dict) -> Any:
    col = get_imports_collection()
    res = col.insert_one(import_doc)
    return res.inserted_id


def update_import_record_repo(import_id: Any, set_fields: dict):
    col = get_imports_collection()
    filter_dict = {"_id": ObjectId(import_id)} if ObjectId.is_valid(str(import_id)) else {"import_batch_id": str(import_id)}
    col.update_one(filter_dict, {"$set": set_fields})


def find_import_record_repo(batch_or_id: str) -> Optional[dict]:
    col = get_imports_collection()
    if ObjectId.is_valid(batch_or_id):
        doc = col.find_one({"_id": ObjectId(batch_or_id)})
        if doc:
            return doc
    doc = col.find_one({"import_batch_id": str(batch_or_id)})
    if doc:
        return doc
    doc = col.find_one({"filename": str(batch_or_id)})
    return doc


def list_import_history_repo(limit: int = 20) -> List[dict]:
    col = get_imports_collection()
    docs = col.find({}).sort("upload_timestamp", -1).limit(limit)
    return [_import_doc_to_dict(d) for d in docs]


def delete_import_record_repo(import_id: Any) -> int:
    col = get_imports_collection()
    filter_dict = {"_id": ObjectId(import_id)} if ObjectId.is_valid(str(import_id)) else {"import_batch_id": str(import_id)}
    res = col.delete_one(filter_dict)
    return res.deleted_count


def insert_procurement_record_repo(record: dict) -> Any:
    col = get_procurement_collection()
    res = col.insert_one(record)
    return res.inserted_id


def insert_expense_record_repo(record: dict) -> Any:
    col = get_expenses_collection()
    res = col.insert_one(record)
    return res.inserted_id


def find_procurement_by_hash(row_hash: str) -> Optional[dict]:
    col = get_procurement_collection()
    return col.find_one({"row_hash": row_hash})


def find_expense_by_hash(row_hash: str) -> Optional[dict]:
    col = get_expenses_collection()
    return col.find_one({"row_hash": row_hash})


def delete_procurements_by_filter(filter_dict: dict) -> int:
    col = get_procurement_collection()
    res = col.delete_many(filter_dict)
    return res.deleted_count


def delete_expenses_by_filter(filter_dict: dict) -> int:
    col = get_expenses_collection()
    res = col.delete_many(filter_dict)
    return res.deleted_count
