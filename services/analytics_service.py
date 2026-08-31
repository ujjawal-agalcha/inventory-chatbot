import logging
from typing import List, Dict, Any

from database.mongodb import (
    get_products_collection,
    get_procurement_collection,
    get_expenses_collection,
    get_imports_collection,
)
from database.repositories.product_repository import (
    get_all_products_from_mongo,
    count_products_in_mongo,
)
from database.repositories.import_repository import (
    list_import_history_repo,
    _procurement_doc_to_dict,
    _expense_doc_to_dict,
)
from services.inventory_service import ensure_permanent_electronic_inventory

logger = logging.getLogger("services.analytics")


def get_inventory_stats() -> dict:
    """Calculate aggregate inventory statistics from MongoDB."""
    col = get_products_collection()
    proc_col = get_procurement_collection()
    exp_col = get_expenses_collection()

    if count_products_in_mongo() == 0:
        ensure_permanent_electronic_inventory()

    all_prods = get_all_products_from_mongo()
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

    if count_products_in_mongo() == 0:
        ensure_permanent_electronic_inventory()

    all_prods = get_all_products_from_mongo()

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

    top_expenses = sorted(all_prods, key=lambda x: x.get("total_expense", 0.0), reverse=True)[:6]
    top_required = sorted(all_prods, key=lambda x: x.get("total_qty_required", 0), reverse=True)[:6]
    recent_proc = list(proc_col.find({}).sort("created_at", -1).limit(8))
    recent_exp = list(exp_col.find({}).sort("created_at", -1).limit(8))
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
        "top_expenses": top_expenses,
        "top_required": top_required,
        "recent_procurements": [_procurement_doc_to_dict(p) for p in recent_proc],
        "recent_expenses": [_expense_doc_to_dict(e) for e in recent_exp],
        "low_stock_items": low_stock,
    }


def get_import_history_list(limit: int = 20) -> List[dict]:
    """Retrieve file import records."""
    return list_import_history_repo(limit)
