from models import InventoryItem, ReorderRequest


def get_all_inventory(db):
    return (
        db.query(InventoryItem)
        .order_by(InventoryItem.name)
        .all()
    )


def get_component(db, name):
    name = name.strip()

    return (
        db.query(InventoryItem)
        .filter(InventoryItem.name.ilike(f"%{name}%"))
        .first()
    )


def search_inventory(db, query):
    query = query.strip()

    if not query:
        return get_all_inventory(db)

    search = f"%{query}%"

    return (
        db.query(InventoryItem)
        .filter(
            (InventoryItem.name.ilike(search))
            | (InventoryItem.category.ilike(search))
            | (InventoryItem.supplier.ilike(search))
        )
        .order_by(InventoryItem.name)
        .all()
    )


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


def get_reorder_requests(db):
    return (
        db.query(ReorderRequest)
        .order_by(ReorderRequest.created_at.desc())
        .all()
    )