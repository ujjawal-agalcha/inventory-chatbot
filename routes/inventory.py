import logging
from datetime import datetime
from typing import List, Optional
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, Response, status

from database.models import User
from schemas.inventory import (
    StockUpdateBody,
    ProductUpdateBody,
    ReorderRequestBody,
)
from services.auth_service import get_current_user
from services.inventory_service import (
    get_all_products,
    get_product,
    search_products,
    get_low_stock_products,
    get_out_of_stock_products,
    get_suppliers_summary,
    update_product_stock,
    update_product,
    create_reorder_request,
    get_all_reorders,
)
from services.analytics_service import get_inventory_stats
from excel.master_sheet import generate_master_sheet_bytes

logger = logging.getLogger("routes.inventory")

router = APIRouter(tags=["Inventory"])


@router.get("/api/inventory")
def inventory_list():
    """Retrieve all Master Inventory items from MongoDB."""
    return get_all_products()


@router.get("/api/inventory/master-sheet/download")
def download_master_sheet(
    user: User = Depends(get_current_user),
):
    """
    Generate and download a fresh Master Sheet from current MongoDB inventory data.
    Requires authenticated company user.
    """
    try:
        excel_bytes = generate_master_sheet_bytes()
        filename = f"Master_Inventory_Sheet_{datetime.now().strftime('%Y-%m-%d')}.xlsx"

        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    except Exception as e:
        logger.exception("Failed to generate master sheet: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to generate master sheet: {str(e)}")


@router.get("/api/inventory/low-stock")
def low_stock():
    """Retrieve low-stock inventory products from MongoDB."""
    return get_low_stock_products()


@router.get("/api/inventory/out-of-stock")
def out_of_stock_items():
    """Retrieve all out-of-stock products."""
    return get_out_of_stock_products()


@router.get("/api/inventory/stats")
def inventory_stats():
    """Retrieve live inventory aggregates from MongoDB."""
    return get_inventory_stats()


@router.get("/api/inventory/component/{name}")
def component_by_path(name: str):
    item = get_product(name)
    if not item:
        raise HTTPException(status_code=404, detail=f"Product '{name}' not found.")
    return item


@router.get("/api/component")
def component_by_query(name: str):
    if not name.strip():
        raise HTTPException(status_code=400, detail="Component name cannot be empty.")
    item = get_product(name)
    if not item:
        raise HTTPException(status_code=404, detail=f"Product '{name}' not found.")
    return item


@router.get("/api/components")
def components_by_category(category: str):
    if not category.strip():
        raise HTTPException(status_code=400, detail="Category cannot be empty.")
    return get_all_products(category=category.strip())


@router.get("/api/inventory/search")
def inventory_search(q: str):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")
    return search_products(q)


@router.put("/api/inventory/{item_id}/stock")
def change_stock(item_id: str, data: StockUpdateBody):
    try:
        item = update_product_stock(item_id, data.stock)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found.")

    return {
        "message": "Stock updated successfully.",
        "item": item,
    }


@router.put("/api/inventory/{item_id}")
def edit_product(
    item_id: str,
    data: ProductUpdateBody,
    user: User = Depends(get_current_user),
):
    """Update any editable fields for an inventory product."""
    update_fields = data.model_dump(exclude_none=True)
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update.")

    try:
        item = update_product(item_id, update_fields)
    except Exception as error:
        logger.exception("Failed to update product: %s", error)
        raise HTTPException(status_code=500, detail="Unable to update inventory. Please try again.")

    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found.")

    return {
        "message": "Product updated successfully.",
        "item": item,
    }


@router.get("/api/inventory/suppliers")
def suppliers_summary():
    """Retrieve supplier distribution summary."""
    return get_suppliers_summary()


@router.post("/api/reorders")
def create_reorder(data: ReorderRequestBody):
    try:
        record = create_reorder_request(
            item_identifier=data.item_id,
            quantity=data.quantity,
            vendor=data.vendor,
            remarks=data.remarks,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if not record:
        raise HTTPException(status_code=404, detail="Product not found for reorder.")

    return {
        **record,
        "message": "Reorder request saved successfully.",
    }


@router.get("/api/reorders")
def list_reorders():
    return get_all_reorders()
