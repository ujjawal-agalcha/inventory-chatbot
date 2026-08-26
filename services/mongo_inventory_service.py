import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
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
        "source_file": doc.get("source_file", ""),
    }


def import_to_dict(doc: dict) -> dict:
    """Format MongoDB import document for API."""
    if not doc:
        return {}
    return {
        "id": str(doc.get("_id", "")),
        "filename": doc.get("filename", ""),
        "file_type": doc.get("file_type", ""),
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
# PRODUCT QUERIES
# ============================================================

def get_all_products(
    category: Optional[str] = None,
    supplier: Optional[str] = None,
    status: Optional[str] = None,
) -> List[dict]:
    """Retrieve all products from MongoDB with optional filters."""
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

    # 4b. Highest scoring token overlap
    best_prod = None
    best_score = 0
    for p in all_prods:
        p_text = " ".join([
            p.get("name", ""),
            p.get("details", ""),
            " ".join(p.get("aliases", [])),
            " ".join(p.get("keywords", [])),
        ]).lower()
        score = sum(1 for t in tokens if t in p_text)
        if score > best_score and score >= 1:
            best_score = score
            best_prod = p

    if best_prod and best_score >= 1:
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
    # Find items where current_stock <= min_stock
    # In MongoDB query, we can fetch all or use $expr
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
        "source_file": "Chatbot Reorder",
        "source_sheet": "Live System",
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
