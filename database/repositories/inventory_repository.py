import logging
from typing import List, Optional
# pyrefly: ignore [missing-import]
from sqlalchemy import or_
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from database.models import InventoryItem, ReorderRequest

logger = logging.getLogger("database.repositories.inventory")


def get_all_sqlite_inventory(db: Session) -> List[InventoryItem]:
    return (
        db.query(InventoryItem)
        .order_by(InventoryItem.name)
        .all()
    )


def get_sqlite_component(db: Session, name: str) -> Optional[InventoryItem]:
    if not name:
        return None
    name = name.strip()
    if not name:
        return None

    # 1. Exact match
    item = db.query(InventoryItem).filter(InventoryItem.name == name).first()
    if item:
        return item

    # 2. Case-insensitive exact match
    item = db.query(InventoryItem).filter(InventoryItem.name.ilike(name)).first()
    if item:
        return item

    # 3. Substring match
    item = db.query(InventoryItem).filter(InventoryItem.name.ilike(f"%{name}%")).first()
    if item:
        return item

    return None


def search_sqlite_inventory(db: Session, query: str) -> List[InventoryItem]:
    if not query:
        return get_all_sqlite_inventory(db)
    query = query.strip().lower()
    if not query:
        return get_all_sqlite_inventory(db)

    full_search = f"%{query}%"
    results = (
        db.query(InventoryItem)
        .filter(
            or_(
                InventoryItem.name.ilike(full_search),
                InventoryItem.category.ilike(full_search),
                InventoryItem.supplier.ilike(full_search),
            )
        )
        .order_by(InventoryItem.name)
        .all()
    )
    if results:
        return results

    stop_words = {
        "how", "many", "much", "is", "are", "there", "in", "the", "stock",
        "available", "availability", "do", "does", "we", "have", "got",
        "currently", "can", "you", "tell", "me", "about", "what", "which",
        "where", "who", "for", "of", "units", "unit", "left", "remaining",
        "please", "show", "give",
    }
    words = [
        word for word in query.replace("-", " ").split()
        if word not in stop_words and len(word) >= 2
    ]
    if not words:
        return []

    conditions = []
    for word in words:
        pattern = f"%{word}%"
        conditions.extend([
            InventoryItem.name.ilike(pattern),
            InventoryItem.category.ilike(pattern),
            InventoryItem.supplier.ilike(pattern),
        ])

    results = (
        db.query(InventoryItem)
        .filter(or_(*conditions))
        .order_by(InventoryItem.name)
        .all()
    )

    scored = []
    for item in results:
        item_text = " ".join([
            item.name or "",
            item.category or "",
            item.supplier or "",
        ]).lower()
        score = sum(1 for word in words if word in item_text)
        scored.append((score, item))

    scored.sort(key=lambda x: (-x[0], x[1].name.lower()))
    return [item for score, item in scored]


def get_sqlite_low_stock_items(db: Session) -> List[InventoryItem]:
    return (
        db.query(InventoryItem)
        .filter(InventoryItem.stock <= InventoryItem.min_stock)
        .order_by(InventoryItem.stock.asc())
        .all()
    )


def update_sqlite_stock(db: Session, item_id: int, new_stock: int) -> Optional[InventoryItem]:
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        return None
    if new_stock < 0:
        raise ValueError("Stock cannot be negative.")
    item.stock = new_stock
    db.commit()
    db.refresh(item)
    return item


def create_sqlite_reorder_request(db: Session, item_id: int, quantity: int) -> Optional[ReorderRequest]:
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        return None
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")

    reorder = ReorderRequest(
        item_id=item.id,
        quantity=quantity,
        supplier=item.supplier,
        status="pending",
    )
    db.add(reorder)
    db.commit()
    db.refresh(reorder)
    return reorder


def get_sqlite_reorder_requests(db: Session) -> List[ReorderRequest]:
    return (
        db.query(ReorderRequest)
        .order_by(ReorderRequest.created_at.desc())
        .all()
    )
