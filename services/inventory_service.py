from models import InventoryItem, ReorderRequest
from sqlalchemy import or_


def get_all_inventory(db):
    return (
        db.query(InventoryItem)
        .order_by(InventoryItem.name)
        .all()
    )


def get_component(db, name):
    """
    Resolve an inventory item by:
    1. Exact name
    2. Case-insensitive exact name
    3. Substring
    4. Individual meaningful words
    """

    if not name:
        return None

    name = name.strip()

    if not name:
        return None

    # ---------------------------------------------------------
    # 1. Exact match
    # ---------------------------------------------------------

    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.name == name)
        .first()
    )

    if item:
        return item

    # ---------------------------------------------------------
    # 2. Case-insensitive exact match
    # ---------------------------------------------------------

    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.name.ilike(name))
        .first()
    )

    if item:
        return item

    # ---------------------------------------------------------
    # 3. Substring match
    # ---------------------------------------------------------

    item = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.name.ilike(f"%{name}%")
        )
        .first()
    )

    if item:
        return item

    return None


def search_inventory(db, query):
    """
    Search inventory intelligently.

    A query such as:

        How many esp32 dev kit are there in stock

    should NOT search the entire sentence.

    Instead, extract meaningful terms and search
    product/category/supplier fields.
    """

    if not query:
        return get_all_inventory(db)

    query = query.strip().lower()

    if not query:
        return get_all_inventory(db)

    # ---------------------------------------------------------
    # First: search the complete query
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # Second: remove common conversational words
    # ---------------------------------------------------------

    stop_words = {
        "how",
        "many",
        "much",
        "is",
        "are",
        "there",
        "in",
        "the",
        "stock",
        "available",
        "availability",
        "do",
        "does",
        "we",
        "have",
        "got",
        "currently",
        "can",
        "you",
        "tell",
        "me",
        "about",
        "what",
        "which",
        "where",
        "who",
        "for",
        "of",
        "units",
        "unit",
        "left",
        "remaining",
        "please",
        "show",
        "give",
    }

    words = [
        word
        for word in query.replace("-", " ").split()
        if word not in stop_words
    ]

    if not words:
        return []

    # ---------------------------------------------------------
    # Third: search individual meaningful words
    # ---------------------------------------------------------

    conditions = []

    for word in words:
        if len(word) < 2:
            continue

        pattern = f"%{word}%"

        conditions.extend([
            InventoryItem.name.ilike(pattern),
            InventoryItem.category.ilike(pattern),
            InventoryItem.supplier.ilike(pattern),
        ])

    if not conditions:
        return []

    results = (
        db.query(InventoryItem)
        .filter(or_(*conditions))
        .order_by(InventoryItem.name)
        .all()
    )

    # ---------------------------------------------------------
    # Rank results by number of matching words
    # ---------------------------------------------------------

    scored = []

    for item in results:

        item_text = " ".join([
            item.name or "",
            item.category or "",
            item.supplier or "",
        ]).lower()

        score = sum(
            1
            for word in words
            if word in item_text
        )

        scored.append((score, item))

    scored.sort(
        key=lambda x: (-x[0], x[1].name.lower())
    )

    return [item for score, item in scored]


def get_low_stock_items(db):
    return (
        db.query(InventoryItem)
        .filter(
            InventoryItem.stock <= InventoryItem.min_stock
        )
        .order_by(InventoryItem.stock.asc())
        .all()
    )


def get_inventory_stats(db):
    items = get_all_inventory(db)

    return {
        "total_components": len(items),
        "total_units": sum(item.stock for item in items),
        "low_stock": sum(
            1
            for item in items
            if item.stock <= item.min_stock
        ),
    }


def update_stock(db, item_id, new_stock):
    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.id == item_id)
        .first()
    )

    if not item:
        return None

    if new_stock < 0:
        raise ValueError("Stock cannot be negative.")

    item.stock = new_stock

    db.commit()
    db.refresh(item)

    return item


def create_reorder_request(db, item_id, quantity):

    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.id == item_id)
        .first()
    )

    if not item:
        return None

    if quantity <= 0:
        raise ValueError(
            "Quantity must be greater than zero."
        )

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


def get_reorder_requests(db):
    return (
        db.query(ReorderRequest)
        .order_by(
            ReorderRequest.created_at.desc()
        )
        .all()
    )