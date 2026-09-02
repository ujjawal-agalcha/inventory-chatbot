import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
# pyrefly: ignore [missing-import]
from bson import ObjectId

from database.repositories.product_repository import (
    get_all_products_from_mongo,
    get_product_by_name_or_norm,
    get_product_by_id,
    search_products_in_mongo,
    get_low_stock_products_from_mongo,
    get_out_of_stock_products_from_mongo,
    update_product_stock_in_mongo,
    update_product_fields_in_mongo,
    count_products_in_mongo,
)
from database.mongodb import (
    get_products_collection,
    get_procurement_collection,
    get_expenses_collection,
)

logger = logging.getLogger("services.inventory")


def ensure_permanent_electronic_inventory():
    """
    Ensure the 39 legitimate electronic equipment products are present in MongoDB
    marked with source_type='permanent_inventory'.
    """
    from scripts.seed_database import seed_mongo_inventory
    return seed_mongo_inventory()


def get_all_products(
    category: Optional[str] = None,
    supplier: Optional[str] = None,
    status: Optional[str] = None,
) -> List[dict]:
    """Retrieve all products from MongoDB with optional filters."""
    if count_products_in_mongo() == 0:
        ensure_permanent_electronic_inventory()
    return get_all_products_from_mongo(category=category, supplier=supplier, status=status)


def get_product(name_or_id: str) -> Optional[dict]:
    """Intelligently resolve a product from MongoDB."""
    if count_products_in_mongo() == 0:
        ensure_permanent_electronic_inventory()
    prod = get_product_by_id(name_or_id)
    if prod:
        return prod
    return get_product_by_name_or_norm(name_or_id)


def search_products(query_str: str, limit: int = 20) -> List[dict]:
    """Search products in MongoDB."""
    if count_products_in_mongo() == 0:
        ensure_permanent_electronic_inventory()
    return search_products_in_mongo(query_str, limit)


def get_low_stock_products() -> List[dict]:
    """Retrieve all products where current_stock <= min_stock."""
    if count_products_in_mongo() == 0:
        ensure_permanent_electronic_inventory()
    return get_low_stock_products_from_mongo()


def get_out_of_stock_products() -> List[dict]:
    """Retrieve all products where current_stock == 0."""
    return get_out_of_stock_products_from_mongo()


def update_product_stock(product_id_or_name: str, new_stock: int) -> Optional[dict]:
    """Update stock for a product in MongoDB."""
    return update_product_stock_in_mongo(product_id_or_name, new_stock)


def update_product(product_id: str, update_fields: dict) -> Optional[dict]:
    """Update editable fields for a product in MongoDB."""
    return update_product_fields_in_mongo(product_id, update_fields)


def get_suppliers_summary() -> List[dict]:
    """Retrieve supplier distribution summary."""
    prods = get_all_products()
    supplier_map = {}
    for p in prods:
        sup = p.get("supplier", "Unknown")
        if sup not in supplier_map:
            supplier_map[sup] = {
                "supplier": sup,
                "product_count": 0,
                "total_units": 0,
                "total_expense": 0.0,
                "products": [],
            }
        supplier_map[sup]["product_count"] += 1
        supplier_map[sup]["total_units"] += p.get("current_stock", 0)
        supplier_map[sup]["total_expense"] += p.get("total_expense", 0.0)
        supplier_map[sup]["products"].append(p.get("name", ""))

    return list(supplier_map.values())


def create_reorder_request(
    item_identifier: str,
    quantity: int,
    vendor: Optional[str] = None,
    remarks: Optional[str] = None,
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

    products_col.update_one(
        {"normalized_name": prod["normalized_name"]},
        {"$inc": {"pending_requirements": quantity, "total_qty_required": quantity}}
    )

    from database.repositories.import_repository import _procurement_doc_to_dict
    return _procurement_doc_to_dict(record)


def get_all_reorders(limit: int = 50) -> List[dict]:
    """Retrieve all reorder/procurement records."""
    proc_col = get_procurement_collection()
    docs = proc_col.find({}).sort("created_at", -1).limit(limit)
    from database.repositories.import_repository import _procurement_doc_to_dict
    return [_procurement_doc_to_dict(d) for d in docs]