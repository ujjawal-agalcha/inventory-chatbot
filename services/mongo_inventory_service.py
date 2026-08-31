import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
# pyrefly: ignore [missing-import]
from bson import ObjectId
import re

from mongo_db import (
    get_products_collection,
    get_procurement_collection,
    get_expenses_collection,
    get_imports_collection,
    is_mock_mode,
)
from services.excel_import_service import normalize_text

logger = logging.getLogger("mongo_inventory")


# ============================================================
# SERIALIZATION HELPERS
# ============================================================

def _id_to_str(obj: Any) -> Any:
    """Convert ObjectId to str recursively in dicts/lists."""
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _id_to_str(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_id_to_str(i) for i in obj]
    return obj


def product_to_dict(doc: dict) -> dict:
    """Format MongoDB product document for API & UI."""
    if not doc:
        return {}
    
    current_stock = doc.get("current_stock", 0)
    min_stock = doc.get("min_stock", 5)
    is_low = current_stock <= min_stock

    return {
        "id": str(doc.get("_id", "")),
        "name": doc.get("name", "Unknown Item"),
        "normalized_name": doc.get("normalized_name", ""),
        "details": doc.get("details", ""),
        "category": doc.get("category", "General"),
        "sub_category": doc.get("sub_category", ""),
        "stock": current_stock,
        "current_stock": current_stock,
        "min_stock": min_stock,
        "unit_price": doc.get("unit_price", 0.0),
        "supplier": doc.get("supplier", "Standard Vendor"),
        "market": doc.get("market", "Local"),
        "status": doc.get("status", "in_stock"),
        "is_low_stock": is_low,
        "total_expense": doc.get("total_expense", 0.0),
        "total_qty_purchased": doc.get("total_qty_purchased", 0),
        "total_qty_required": doc.get("total_qty_required", 0),
        "pending_requirements": doc.get("pending_requirements", 0),
        "keywords": doc.get("keywords", []),
        "aliases": doc.get("aliases", []),
        "source_type": doc.get("source_type", "permanent_inventory"),
        "created_by_import_id": str(doc.get("created_by_import_id")) if doc.get("created_by_import_id") else None,
        "import_batch_ids": [str(b) for b in doc.get("import_batch_ids", [])],
        "source_files": doc.get("source_files", []),
        "last_updated": (
            doc["updated_at"].isoformat()
            if isinstance(doc.get("updated_at"), datetime)
            else str(doc.get("updated_at", ""))
        ),
    }


def procurement_to_dict(doc: dict) -> dict:
    """Format MongoDB procurement document for API."""
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


def expense_to_dict(doc: dict) -> dict:
    """Format MongoDB expense document for API."""
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


def import_to_dict(doc: dict) -> dict:
    """Format MongoDB import document for API."""
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


# ============================================================
# PERMANENT ELECTRONIC INVENTORY GUARANTEE
# ============================================================

def ensure_permanent_electronic_inventory():
    """
    Ensure the 39 legitimate electronic equipment products are present in MongoDB
    marked with source_type='permanent_inventory'.
    """
    from seed_data import seed_mongo_inventory
    return seed_mongo_inventory()


# ============================================================
# PRODUCT QUERIES
# ============================================================

def get_all_products(
    category: Optional[str] = None,
    supplier: Optional[str] = None,
    status: Optional[str] = None,
) -> List[dict]:
    """Retrieve all products from MongoDB with optional filters."""
    # Ensure baseline electronic inventory is present
    if get_products_collection().count_documents({}) == 0:
        ensure_permanent_electronic_inventory()

    query = {}
    if category:
        query["category"] = {"$regex": f"^{re.escape(category)}$", "$options": "i"}
    if supplier:
        query["supplier"] = {"$regex": f"^{re.escape(supplier)}$", "$options": "i"}
    if status:
        query["status"] = status

    docs = get_products_collection().find(query).sort("name", 1)
    return [product_to_dict(d) for d in docs]


def get_product(name: str) -> Optional[dict]:
    """
    Intelligently resolve a product from MongoDB:
    1. Exact normalized_name
    2. Case-insensitive exact name
    3. Alias match
    4. Substring in name, details, aliases, or keywords
    5. Token intersection
    """
    if not name:
        return None
    
    clean = str(name).strip()
    norm = normalize_text(clean)
    if not norm:
        return None

    col = get_products_collection()
    if col.count_documents({}) == 0:
        ensure_permanent_electronic_inventory()

    # 1. Exact normalized name
    doc = col.find_one({"normalized_name": norm})
    if doc:
        return product_to_dict(doc)

    # 2. Case-insensitive exact match on name
    doc = col.find_one({"name": {"$regex": f"^{re.escape(clean)}$", "$options": "i"}})
    if doc:
        return product_to_dict(doc)

    # 3. Matches in aliases array
    doc = col.find_one({"aliases": norm})
    if doc:
        return product_to_dict(doc)

    # 4. Search across all products in MongoDB
    all_prods = list(col.find({}))
    tokens = set(norm.split())

    # 4a. Check if any product has an alias, details, or name that contains norm or vice versa
    for p in all_prods:
        p_norm = p.get("normalized_name", "")
        p_details = normalize_text(p.get("details", ""))
        p_aliases = [normalize_text(a) for a in p.get("aliases", [])]
        p_keywords = set(p.get("keywords", []))

        if p_norm and (p_norm in norm or norm in p_norm):
            return product_to_dict(p)

        if p_details and (p_details in norm or norm in p_details):
            return product_to_dict(p)

        for alias in p_aliases:
            if alias and (alias in norm or norm in alias):
                return product_to_dict(p)

        # Check keyword match
        if tokens and (tokens.issubset(p_keywords) or (tokens & p_keywords and len(tokens & p_keywords) >= len(tokens))):
            return product_to_dict(p)

    # 4b. High confidence token overlap
    best_prod = None
    best_score = 0
    min_required_score = max(2, int(len(tokens) * 0.5)) if len(tokens) >= 2 else 1

    for p in all_prods:
        p_text = " ".join([
            p.get("name", ""),
            p.get("details", ""),
            " ".join(p.get("aliases", [])),
            " ".join(p.get("keywords", [])),
        ]).lower()
        score = sum(1 for t in tokens if t in p_text)
        if score > best_score and score >= min_required_score:
            best_score = score
            best_prod = p

    if best_prod and best_score >= min_required_score:
        return product_to_dict(best_prod)

    return None


def search_products(query_str: str, limit: int = 20) -> List[dict]:
    """
    Intelligently search products in MongoDB by tokens across name, category, supplier, details.
    """
    if not query_str:
        return get_all_products()

    norm_q = normalize_text(query_str)
    if not norm_q:
        return get_all_products()

    col = get_products_collection()
    if col.count_documents({}) == 0:
        ensure_permanent_electronic_inventory()
    
    # Check exact product match first
    exact = get_product(query_str)
    if exact:
        return [exact]

    # Stop words removal for search tokens
    stop_words = {
        "how", "many", "much", "is", "are", "there", "in", "stock", "available",
        "do", "we", "have", "got", "the", "a", "an", "what", "which", "please",
        "tell", "me", "about", "show", "give", "current", "units", "left", "who", "supplies"
    }
    tokens = [t for t in norm_q.split() if t not in stop_words and len(t) >= 2]
    
    if not tokens:
        tokens = norm_q.split()

    clauses = []
    for token in tokens:
        pattern = {"$regex": re.escape(token), "$options": "i"}
        clauses.append({"normalized_name": pattern})
        clauses.append({"name": pattern})
        clauses.append({"category": pattern})
        clauses.append({"supplier": pattern})
        clauses.append({"details": pattern})
        clauses.append({"aliases": pattern})
        clauses.append({"keywords": pattern})

    docs = list(col.find({"$or": clauses}))

    # Score and rank matching products
    scored = []
    for doc in docs:
        item_text = " ".join([
            doc.get("name", ""),
            doc.get("category", ""),
            doc.get("supplier", ""),
            doc.get("details", ""),
            " ".join(doc.get("aliases", [])),
            " ".join(doc.get("keywords", [])),
        ]).lower()

        score = sum(1 for token in tokens if token in item_text)
        if norm_q in item_text:
            score += 5
        scored.append((score, doc))

    scored.sort(key=lambda x: -x[0])
    return [product_to_dict(doc) for score, doc in scored[:limit]]


def get_low_stock_products() -> List[dict]:
    """Retrieve all products where current_stock <= min_stock."""
    col = get_products_collection()
    if col.count_documents({}) == 0:
        ensure_permanent_electronic_inventory()

    try:
        docs = col.find({"$expr": {"$lte": ["$current_stock", "$min_stock"]}}).sort("current_stock", 1)
        return [product_to_dict(d) for d in docs]
    except Exception:
        all_prods = list(col.find({}))
        low = [d for d in all_prods if d.get("current_stock", 0) <= d.get("min_stock", 5)]
        low.sort(key=lambda x: x.get("current_stock", 0))
        return [product_to_dict(d) for d in low]


def get_inventory_stats() -> dict:
    """Calculate aggregate inventory statistics from MongoDB."""
    col = get_products_collection()
    proc_col = get_procurement_collection()
    exp_col = get_expenses_collection()

    if col.count_documents({}) == 0:
        ensure_permanent_electronic_inventory()

    all_prods = list(col.find({}))
    total_components = len(all_prods)
    total_units = sum(p.get("current_stock", 0) for p in all_prods)
    low_stock_cnt = sum(1 for p in all_prods if p.get("current_stock", 0) <= p.get("min_stock", 5))
    out_of_stock_cnt = sum(1 for p in all_prods if p.get("current_stock", 0) == 0)
    total_expenses = sum(p.get("total_expense", 0.0) for p in all_prods)
    total_proc_requests = proc_col.count_documents({})
    pending_proc_requests = proc_col.count_documents({"order_status": {"$regex": "^pending$", "$options": "i"}})
    categories = len(set(p.get("category", "") for p in all_prods if p.get("category")))

    return {
        "total_components": total_components,
        "total_units": total_units,
        "low_stock": low_stock_cnt,
        "out_of_stock": out_of_stock_cnt,
        "total_expenses": round(total_expenses, 2),
        "total_proc_requests": total_proc_requests,
        "pending_proc_requests": pending_proc_requests,
        "categories_count": categories,
    }


def get_dashboard_analytics() -> dict:
    """Generate comprehensive analytics for the dashboard."""
    col = get_products_collection()
    proc_col = get_procurement_collection()
    exp_col = get_expenses_collection()

    if col.count_documents({}) == 0:
        ensure_permanent_electronic_inventory()

    all_prods = list(col.find({}))

    # Category breakdown
    category_map = {}
    for p in all_prods:
        cat = p.get("category", "General")
        if cat not in category_map:
            category_map[cat] = {"count": 0, "units": 0, "total_expense": 0.0}
        category_map[cat]["count"] += 1
        category_map[cat]["units"] += p.get("current_stock", 0)
        category_map[cat]["total_expense"] += p.get("total_expense", 0.0)

    # Supplier breakdown
    supplier_map = {}
    for p in all_prods:
        sup = p.get("supplier", "Standard Vendor")
        if sup not in supplier_map:
            supplier_map[sup] = {"count": 0, "units": 0, "total_expense": 0.0}
        supplier_map[sup]["count"] += 1
        supplier_map[sup]["units"] += p.get("current_stock", 0)
        supplier_map[sup]["total_expense"] += p.get("total_expense", 0.0)

    # Monthly expense breakdown
    monthly_expenses = {}
    for exp in exp_col.find({}):
        month = exp.get("expense_month") or "General"
        monthly_expenses[month] = monthly_expenses.get(month, 0.0) + exp.get("amount", 0.0)

    # Top expenses
    top_expenses = sorted(all_prods, key=lambda x: x.get("total_expense", 0.0), reverse=True)[:6]

    # Top required
    top_required = sorted(all_prods, key=lambda x: x.get("total_qty_required", 0), reverse=True)[:6]

    # Recent procurements
    recent_proc = list(proc_col.find({}).sort("created_at", -1).limit(8))

    # Recent expenses
    recent_exp = list(exp_col.find({}).sort("created_at", -1).limit(8))

    # Low stock items
    low_stock = [p for p in all_prods if p.get("current_stock", 0) <= p.get("min_stock", 5)]
    low_stock.sort(key=lambda x: x.get("current_stock", 0))

    return {
        "stats": get_inventory_stats(),
        "categories": [
            {"category": k, "count": v["count"], "units": v["units"], "expense": round(v["total_expense"], 2)}
            for k, v in category_map.items()
        ],
        "suppliers": [
            {"supplier": k, "count": v["count"], "units": v["units"], "expense": round(v["total_expense"], 2)}
            for k, v in supplier_map.items()
        ],
        "monthly_expenses": [
            {"month": k, "amount": round(v, 2)}
            for k, v in monthly_expenses.items()
        ],
        "top_expenses": [product_to_dict(p) for p in top_expenses],
        "top_required": [product_to_dict(p) for p in top_required],
        "recent_procurements": [procurement_to_dict(p) for p in recent_proc],
        "recent_expenses": [expense_to_dict(e) for e in recent_exp],
        "low_stock_items": [product_to_dict(p) for p in low_stock],
    }


def update_product_stock(product_id_or_name: str, new_stock: int) -> Optional[dict]:
    """Update stock for a product in MongoDB."""
    if new_stock < 0:
        raise ValueError("Stock cannot be negative.")

    col = get_products_collection()
    query = {}
    if ObjectId.is_valid(product_id_or_name):
        query = {"_id": ObjectId(product_id_or_name)}
    else:
        norm = normalize_text(product_id_or_name)
        query = {"$or": [{"normalized_name": norm}, {"name": product_id_or_name}]}

    doc = col.find_one(query)
    if not doc:
        return None

    min_stock = doc.get("min_stock", 5)
    status_str = "out_of_stock" if new_stock == 0 else ("low_stock" if new_stock <= min_stock else "in_stock")

    col.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "current_stock": new_stock,
                "status": status_str,
                "updated_at": datetime.utcnow(),
            }
        }
    )

    updated = col.find_one({"_id": doc["_id"]})
    return product_to_dict(updated)


def update_product(product_id: str, update_fields: dict) -> Optional[dict]:
    """Update any editable fields for a product in MongoDB."""
    col = get_products_collection()

    if not ObjectId.is_valid(product_id):
        return None

    doc = col.find_one({"_id": ObjectId(product_id)})
    if not doc:
        return None

    allowed_fields = {
        "name", "category", "sub_category", "current_stock", "min_stock",
        "unit_price", "supplier", "market", "details", "status",
    }

    mongo_set = {"updated_at": datetime.utcnow()}
    for key, value in update_fields.items():
        if key in allowed_fields and value is not None:
            mongo_set[key] = value

    # If name changed, update normalized_name and aliases
    if "name" in mongo_set:
        new_norm = normalize_text(mongo_set["name"])
        mongo_set["normalized_name"] = new_norm

    # Recalculate status based on stock
    stock = mongo_set.get("current_stock", doc.get("current_stock", 0))
    min_s = mongo_set.get("min_stock", doc.get("min_stock", 5))
    if isinstance(stock, (int, float)) and isinstance(min_s, (int, float)):
        mongo_set["status"] = (
            "out_of_stock" if stock == 0
            else ("low_stock" if stock <= min_s else "in_stock")
        )

    col.update_one({"_id": doc["_id"]}, {"$set": mongo_set})
    updated = col.find_one({"_id": doc["_id"]})
    return product_to_dict(updated)


def get_out_of_stock_products() -> List[dict]:
    """Retrieve all products where current_stock == 0."""
    col = get_products_collection()
    docs = col.find({"current_stock": 0}).sort("name", 1)
    return [product_to_dict(d) for d in docs]


def get_suppliers_summary() -> List[dict]:
    """Retrieve supplier distribution summary."""
    col = get_products_collection()
    all_prods = list(col.find({}))
    supplier_map = {}
    for p in all_prods:
        sup = p.get("supplier", "Unknown")
        if sup not in supplier_map:
            supplier_map[sup] = {"supplier": sup, "product_count": 0, "total_units": 0, "total_expense": 0.0, "products": []}
        supplier_map[sup]["product_count"] += 1
        supplier_map[sup]["total_units"] += p.get("current_stock", 0)
        supplier_map[sup]["total_expense"] += p.get("total_expense", 0.0)
        supplier_map[sup]["products"].append(p.get("name", ""))

    return list(supplier_map.values())


def create_reorder_request(
    item_identifier: str,
    quantity: int,
    vendor: Optional[str] = None,
    remarks: Optional[str] = None
) -> Optional[dict]:
    """Create a new procurement / reorder request record in MongoDB."""
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")

    prod = get_product(item_identifier)
    if not prod:
        return None

    proc_col = get_procurement_collection()
    products_col = get_products_collection()

    unit_price = prod.get("unit_price", 0.0)
    amount = quantity * unit_price
    supplier = vendor or prod.get("supplier", "Standard Vendor")
    date_now = datetime.utcnow()
    date_str = date_now.strftime("%Y-%m-%d")

    row_hash = f"reorder_{prod['id']}_{quantity}_{date_now.timestamp()}"

    record = {
        "product_id": ObjectId(prod["id"]) if ObjectId.is_valid(prod["id"]) else prod["id"],
        "product_name": prod["name"],
        "normalized_name": prod["normalized_name"],
        "details": prod.get("details", ""),
        "quantity": quantity,
        "unit_price": unit_price,
        "amount": amount,
        "market": prod.get("market", "Direct"),
        "order_date": date_now,
        "order_date_str": date_str,
        "order_status": "Pending",
        "vendor_name": supplier,
        "approved_by": "System Reorder",
        "remarks": remarks or "Automated reorder from Chatbot",
        "requirement_issued_by": "AI Assistant",
        "url": "",
        "source_type": "manual_reorder",
        "source_file": "Chatbot Reorder",
        "source_sheet": "Live System",
        "import_id": None,
        "import_batch_id": None,
        "row_hash": row_hash,
        "created_at": date_now,
    }

    res = proc_col.insert_one(record)
    record["_id"] = res.inserted_id

    # Update product pending requirements in MongoDB
    products_col.update_one(
        {"normalized_name": prod["normalized_name"]},
        {"$inc": {"pending_requirements": quantity, "total_qty_required": quantity}}
    )

    return procurement_to_dict(record)


def get_all_reorders(limit: int = 50) -> List[dict]:
    """Retrieve all reorder/procurement records."""
    proc_col = get_procurement_collection()
    docs = proc_col.find({}).sort("created_at", -1).limit(limit)
    return [procurement_to_dict(d) for d in docs]


def get_import_history_list(limit: int = 20) -> List[dict]:
    """Retrieve file import records."""
    imports_col = get_imports_collection()
    docs = imports_col.find({}).sort("upload_timestamp", -1).limit(limit)
    return [import_to_dict(d) for d in docs]


# ============================================================
# SAFE IMPORT BATCH CLEANUP & SAMPLE DATA REMOVAL
# ============================================================

def _resolve_import_doc(batch_or_id: str) -> Optional[dict]:
    """Find import document by ObjectId or string batch id."""
    imports_col = get_imports_collection()
    if ObjectId.is_valid(batch_or_id):
        doc = imports_col.find_one({"_id": ObjectId(batch_or_id)})
        if doc:
            return doc
    doc = imports_col.find_one({"import_batch_id": str(batch_or_id)})
    if doc:
        return doc
    doc = imports_col.find_one({"filename": str(batch_or_id)})
    return doc


def preview_import_deletion(batch_or_id: str) -> Dict[str, Any]:
    """
    Preview what records will be deleted or updated before executing deletion.
    """
    import_doc = _resolve_import_doc(batch_or_id)
    if not import_doc:
        raise ValueError(f"Import record '{batch_or_id}' not found.")

    imp_id = import_doc["_id"]
    batch_str = str(import_doc.get("import_batch_id", imp_id))
    filename = import_doc.get("filename", "")

    proc_col = get_procurement_collection()
    exp_col = get_expenses_collection()
    prod_col = get_products_collection()

    # Match procurement records
    proc_query = {
        "$or": [
            {"import_id": imp_id},
            {"import_id": batch_str},
            {"import_batch_id": batch_str},
            {"source_file": filename},
        ]
    }
    proc_count = proc_col.count_documents(proc_query)

    # Match expense records
    exp_query = {
        "$or": [
            {"import_id": imp_id},
            {"import_id": batch_str},
            {"import_batch_id": batch_str},
            {"source_file": filename},
        ]
    }
    exp_count = exp_col.count_documents(exp_query)

    # Products created exclusively by this import (will be deleted)
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

    # Products that are permanent or updated by multiple imports (will be preserved/recalculated)
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
    import_doc = _resolve_import_doc(batch_or_id)
    if not import_doc:
        raise ValueError(f"Import record '{batch_or_id}' not found.")

    imp_id = import_doc["_id"]
    batch_str = str(import_doc.get("import_batch_id", imp_id))
    filename = import_doc.get("filename", "")

    proc_col = get_procurement_collection()
    exp_col = get_expenses_collection()
    prod_col = get_products_collection()
    imports_col = get_imports_collection()

    # 1. Delete procurement records
    proc_del_res = proc_col.delete_many({
        "$or": [
            {"import_id": imp_id},
            {"import_id": batch_str},
            {"import_batch_id": batch_str},
            {"source_file": filename},
        ]
    })

    # 2. Delete expense records
    exp_del_res = exp_col.delete_many({
        "$or": [
            {"import_id": imp_id},
            {"import_id": batch_str},
            {"import_batch_id": batch_str},
            {"source_file": filename},
        ]
    })

    # 3. Delete products created exclusively by this import
    # Never delete permanent inventory!
    exclusive_prods_query = {
        "source_type": "excel_import",
        "$or": [
            {"created_by_import_id": batch_str},
            {"created_by_import_id": str(imp_id)},
            {"source_files": [filename]},
        ]
    }
    prod_del_res = prod_col.delete_many(exclusive_prods_query)

    # 4. Clean up references in remaining products (remove filename and batch id)
    remaining_prods = prod_col.find({
        "$or": [
            {"source_files": filename},
            {"import_batch_ids": batch_str},
        ]
    })
    for p in remaining_prods:
        new_sources = [s for s in p.get("source_files", []) if s != filename]
        new_batches = [b for b in p.get("import_batch_ids", []) if str(b) != batch_str]
        
        # Recalculate requirements / expenses from remaining records
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

    # 5. Delete import history entry
    imports_col.delete_one({"_id": imp_id})

    # Ensure baseline electronic inventory is intact
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
        "status": "deleted"
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

    # Identify sample imports by filename or pattern
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

    # Also clean any orphaned sample procurement/expense records if filename matches sample
    orphan_proc_del = proc_col.delete_many({
        "source_file": {"$regex": "sample", "$options": "i"}
    })
    orphan_exp_del = exp_col.delete_many({
        "source_file": {"$regex": "sample", "$options": "i"}
    })

    # Remove any products that have source_type == 'excel_import' and were sourced from sample files
    sample_prods_del = prod_col.delete_many({
        "source_type": "excel_import",
        "source_files": {"$elemMatch": {"$regex": "sample", "$options": "i"}},
    })

    # Guarantee all 39 legitimate electronic equipment products are preserved in MongoDB
    ensure_permanent_electronic_inventory()

    return {
        "success": True,
        "cleaned_import_batches": results,
        "orphan_procurements_removed": orphan_proc_del.deleted_count,
        "orphan_expenses_removed": orphan_exp_del.deleted_count,
        "sample_products_removed": sample_prods_del.deleted_count,
        "permanent_products_count": prod_col.count_documents({"source_type": "permanent_inventory"}),
    }
