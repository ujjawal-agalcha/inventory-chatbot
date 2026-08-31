from typing import Optional, List, Any
from pydantic import BaseModel, Field


class ReorderRequestBody(BaseModel):
    item_id: str
    quantity: int = Field(gt=0, description="Quantity to reorder")
    vendor: Optional[str] = None
    remarks: Optional[str] = None


class StockUpdateBody(BaseModel):
    stock: int = Field(ge=0, description="New stock quantity")


class ProductUpdateBody(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    current_stock: Optional[int] = Field(None, ge=0)
    min_stock: Optional[int] = Field(None, ge=0)
    unit_price: Optional[float] = Field(None, ge=0)
    supplier: Optional[str] = None
    market: Optional[str] = None
    details: Optional[str] = None


class ProductResponse(BaseModel):
    id: str
    name: str
    normalized_name: str
    category: str
    sub_category: Optional[str] = None
    stock: int
    current_stock: int
    min_stock: int
    unit_price: float
    supplier: str
    market: Optional[str] = None
    status: str
    is_low_stock: bool
    total_expense: float = 0.0
    total_qty_purchased: int = 0
    total_qty_required: int = 0
    pending_requirements: int = 0
    details: Optional[str] = None
    last_updated: Optional[str] = None
