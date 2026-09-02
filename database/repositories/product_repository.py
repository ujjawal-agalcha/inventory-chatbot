import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
# pyrefly: ignore [missing-import]
from bson import ObjectId

from database.mongodb import get_products_collection

logger = logging.getLogger("database.repositories.product")


def _doc_to_dict(doc: dict) -> dict:
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


def count_products_in_mongo(filter_dict: Optional[dict] = None) -> int:
    col = get_products_collection()
    return col.count_documents(filter_dict or {})


def get_all_products_from_mongo(
    category: Optional[str] = None,
    supplier: Optional[str] = None,
    status: Optional[str] = None,
) -> List[dict]:
    col = get_products_collection()
    query = {}
    if category:
        query["category"] = {"$regex": f"^{re.escape(category)}$", "$options": "i"}
    if supplier:
        query["supplier"] = {"$regex": f"^{re.escape(supplier)}$", "$options": "i"}
    if status:
        query["status"] = status

    docs = col.find(query).sort("name", 1)
    return [_doc_to_dict(d) for d in docs]


def get_product_by_id(product_id: str) -> Optional[dict]:
    if not ObjectId.is_valid(product_id):
        return None
    col = get_products_collection()
    doc = col.find_one({"_id": ObjectId(product_id)})
    return _doc_to_dict(doc) if doc else None


def get_product_by_name_or_norm(name: str) -> Optional[dict]:
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
        return _doc_to_dict(doc)

    # 2. Case-insensitive exact match
    doc = col.find_one({"name": {"$regex": f"^{re.escape(clean)}$", "$options": "i"}})
    if doc:
        return _doc_to_dict(doc)

    # 3. Aliases array
    doc = col.find_one({"aliases": norm})
    if doc:
        return _doc_to_dict(doc)

    # 4. Search across all products
    all_prods = list(col.find({}))
    tokens = set(norm.split())

    for p in all_prods:
        p_norm = p.get("normalized_name", "")
        p_details = normalize_text(p.get("details", ""))
        p_aliases = [normalize_text(a) for a in p.get("aliases", [])]
        p_keywords = set(p.get("keywords", []))

        if p_norm and (p_norm in norm or norm in p_norm):
            return _doc_to_dict(p)
        if p_details and (p_details in norm or norm in p_details):
            return _doc_to_dict(p)
        for alias in p_aliases:
            if alias and (alias in norm or norm in alias):
                return _doc_to_dict(p)
        if tokens and (tokens.issubset(p_keywords) or (tokens & p_keywords and len(tokens & p_keywords) >= len(tokens))):
            return _doc_to_dict(p)

    # 5. Token overlap ranking
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
        return _doc_to_dict(best_prod)

    return None


def search_products_in_mongo(query_str: str, limit: int = 20) -> List[dict]:
    if not query_str:
        return get_all_products_from_mongo()
    norm_q = normalize_text(query_str)
    if not norm_q:
        return get_all_products_from_mongo()

    col = get_products_collection()
    exact = get_product_by_name_or_norm(query_str)
    if exact:
        return [exact]

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
    return [_doc_to_dict(doc) for score, doc in scored[:limit]]


def get_low_stock_products_from_mongo() -> List[dict]:
    col = get_products_collection()
    try:
        docs = col.find({"$expr": {"$lte": ["$current_stock", "$min_stock"]}}).sort("current_stock", 1)
        return [_doc_to_dict(d) for d in docs]
    except Exception:
        all_prods = list(col.find({}))
        low = [d for d in all_prods if d.get("current_stock", 0) <= d.get("min_stock", 5)]
        low.sort(key=lambda x: x.get("current_stock", 0))
        return [_doc_to_dict(d) for d in low]


def get_out_of_stock_products_from_mongo() -> List[dict]:
    col = get_products_collection()
    docs = col.find({"current_stock": 0}).sort("name", 1)
    return [_doc_to_dict(d) for d in docs]


def update_product_stock_in_mongo(product_id_or_name: str, new_stock: int) -> Optional[dict]:
    if new_stock < 0:
        raise ValueError("Stock cannot be negative.")
    col = get_products_collection()
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
        {"$set": {"current_stock": new_stock, "status": status_str, "updated_at": datetime.utcnow()}}
    )
    return _doc_to_dict(col.find_one({"_id": doc["_id"]}))


def update_product_fields_in_mongo(product_id: str, update_fields: dict) -> Optional[dict]:
    if not ObjectId.is_valid(product_id):
        return None
    col = get_products_collection()
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

    if "name" in mongo_set:
        mongo_set["normalized_name"] = normalize_text(mongo_set["name"])

    stock = mongo_set.get("current_stock", doc.get("current_stock", 0))
    min_s = mongo_set.get("min_stock", doc.get("min_stock", 5))
    if isinstance(stock, (int, float)) and isinstance(min_s, (int, float)):
        mongo_set["status"] = "out_of_stock" if stock == 0 else ("low_stock" if stock <= min_s else "in_stock")

    col.update_one({"_id": doc["_id"]}, {"$set": mongo_set})
    return _doc_to_dict(col.find_one({"_id": doc["_id"]}))


def upsert_product_in_mongo(filter_dict: dict, set_fields: dict, inc_fields: Optional[dict] = None) -> Any:
    col = get_products_collection()
    update_doc = {"$set": set_fields}
    if inc_fields:
        update_doc["$inc"] = inc_fields
    return col.update_one(filter_dict, update_doc, upsert=True)


def delete_products_by_filter(filter_dict: dict) -> int:
    col = get_products_collection()
    res = col.delete_many(filter_dict)
    return res.deleted_count
