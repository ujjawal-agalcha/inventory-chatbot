from sqlalchemy.orm import Session
from sqlalchemy import func

from models import InventoryItem, ReorderRequest


# ============================================================
# GET ALL INVENTORY
# ============================================================

def get_all_inventory(db: Session):
    return (
        db.query(InventoryItem)
        .order_by(InventoryItem.name)
        .all()
    )


# ============================================================
# GET COMPONENT BY NAME
# ============================================================

def get_component(db: Session, name: str):

    return (
        db.query(InventoryItem)
        .filter(
            func.lower(InventoryItem.name)
            == name.strip().lower()
        )
        .first()
    )


# ============================================================
# SEARCH INVENTORY
# ============================================================

def search_inventory(db: Session, query: str):

    search_term = f"%{query.strip()}%"

    return (
        db.query(InventoryItem)
        .filter(
            InventoryItem.name.ilike(search_term)
            |
            InventoryItem.category.ilike(search_term)
        )
        .order_by(InventoryItem.name)
        .all()
    )


# ============================================================
# LOW STOCK ITEMS
# ============================================================

def get_low_stock_items(db: Session):

    return (
        db.query(InventoryItem)
        .filter(
            InventoryItem.stock
            <= InventoryItem.min_stock
        )
        .order_by(InventoryItem.stock)
        .all()
    )


# ============================================================
# GET INVENTORY STATISTICS
# ============================================================

def get_inventory_stats(db: Session):

    total_products = (
        db.query(InventoryItem)
        .count()
    )

    low_stock_items = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.stock
            <= InventoryItem.min_stock
        )
        .count()
    )

    suppliers = (
        db.query(
            func.count(
                func.distinct(
                    InventoryItem.supplier
                )
            )
        )
        .scalar()
    )

    categories = (
        db.query(
            func.count(
                func.distinct(
                    InventoryItem.category
                )
            )
        )
        .scalar()
    )

    return {
        "total_products": total_products,
        "low_stock_items": low_stock_items,
        "suppliers": suppliers or 0,
        "categories": categories or 0,
    }


# ============================================================
# CREATE REORDER REQUEST
# ============================================================

def create_reorder_request(
    db: Session,
    item_id: int,
    quantity: int,
):

    item = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.id == item_id
        )
        .first()
    )

    if not item:
        return None

    if quantity <= 0:
        raise ValueError(
            "Reorder quantity must be greater than 0."
        )

    reorder = ReorderRequest(
        item_id=item.id,
        quantity=quantity,
        supplier=item.supplier,
        status="Pending",
    )

    db.add(reorder)
    db.commit()
    db.refresh(reorder)

    return reorder


# ============================================================
# GET ALL REORDER REQUESTS
# ============================================================

def get_reorder_requests(db: Session):

    return (
        db.query(ReorderRequest)
        .order_by(
            ReorderRequest.created_at.desc()
        )
        .all()
    )


# ============================================================
# UPDATE STOCK
# ============================================================

def update_stock(
    db: Session,
    item_id: int,
    new_stock: int,
):

    item = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.id == item_id
        )
        .first()
    )

    if not item:
        return None

    if new_stock < 0:
        raise ValueError(
            "Stock cannot be negative."
        )

    item.stock = new_stock

    db.commit()
    db.refresh(item)

    return item