from fastmcp import FastMCP

from models import SessionLocal
from services.inventory_service import (
    get_all_inventory,
    get_component,
    search_inventory,
    get_low_stock_items,
    get_inventory_stats,
    create_reorder_request,
)


mcp = FastMCP("Inventory MCP Server")


def inventory_to_dict(item):
    return {
        "id": item.id,
        "name": item.name,
        "category": item.category,
        "stock": item.stock,
        "min_stock": item.min_stock,
        "supplier": item.supplier,
        "last_updated": (
            item.updated_at.isoformat()
            if item.updated_at
            else None
        ),
    }


@mcp.tool
def get_product_stock(product_name: str) -> dict:
    """
    Get the current stock of one specific inventory product.
    """

    db = SessionLocal()

    try:
        item = get_component(db, product_name)

        if not item:
            return {
                "found": False,
                "message": f"Product '{product_name}' was not found.",
            }

        return {
            "found": True,
            "product": item.name,
            "stock": item.stock,
            "minimum_stock": item.min_stock,
            "supplier": item.supplier,
            "is_low_stock": item.stock <= item.min_stock,
            "is_out_of_stock": item.stock == 0,
        }

    finally:
        db.close()


@mcp.tool
def get_product_stock(product_name: str) -> dict:
    """
    Get the current stock of a specific inventory product.

    The tool first tries the existing exact database lookup.
    If that fails, it performs a case-insensitive partial
    search so natural product names such as "ESP32-CAM" can
    still be resolved.
    """

    db = SessionLocal()

    try:
        # ----------------------------------------------------
        # 1. Try the existing exact lookup
        # ----------------------------------------------------

        item = get_component(
            db,
            product_name.strip(),
        )

        # ----------------------------------------------------
        # 2. If exact lookup fails, search inventory
        # ----------------------------------------------------

        if not item:
            matches = search_inventory(
                db,
                product_name.strip(),
            )

            if matches:
                # Prefer an exact case-insensitive match
                exact_match = next(
                    (
                        match
                        for match in matches
                        if match.name.strip().lower()
                        == product_name.strip().lower()
                    ),
                    None,
                )

                item = exact_match or matches[0]

        # ----------------------------------------------------
        # 3. Product still not found
        # ----------------------------------------------------

        if not item:
            return {
                "found": False,
                "message": (
                    f"No inventory product matching "
                    f"'{product_name}' was found."
                ),
            }

        # ----------------------------------------------------
        # 4. Return live inventory information
        # ----------------------------------------------------

        return {
            "found": True,
            "product": item.name,
            "stock": item.stock,
            "minimum_stock": item.min_stock,
            "supplier": item.supplier,
            "is_low_stock": (
                item.stock <= item.min_stock
            ),
            "is_out_of_stock": (
                item.stock == 0
            ),
        }

    finally:
        db.close()


@mcp.tool
def search_products(query: str) -> list[dict]:
    """
    Search inventory products by name or category.
    """

    db = SessionLocal()

    try:
        items = search_inventory(db, query)

        return [
            inventory_to_dict(item)
            for item in items[:20]
        ]

    finally:
        db.close()


@mcp.tool
def get_low_stock_products() -> list[dict]:
    """
    Return products currently at or below their minimum stock level.
    """

    db = SessionLocal()

    try:
        items = get_low_stock_items(db)

        return [
            inventory_to_dict(item)
            for item in items
        ]

    finally:
        db.close()


@mcp.tool
def get_inventory_statistics() -> dict:
    """
    Return overall inventory statistics.
    """

    db = SessionLocal()

    try:
        return get_inventory_stats(db)

    finally:
        db.close()


@mcp.tool
def get_all_products() -> list[dict]:
    """
    Return all products in the inventory.
    """

    db = SessionLocal()

    try:
        items = get_all_inventory(db)

        return [
            inventory_to_dict(item)
            for item in items
        ]

    finally:
        db.close()


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="127.0.0.1",
        port=8001,
    )