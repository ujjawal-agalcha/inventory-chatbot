from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class InventoryStatsResponse(BaseModel):
    total_components: int
    total_units: int
    low_stock: int
    out_of_stock: int
    total_expenses: float
    total_proc_requests: int
    pending_proc_requests: int
    categories_count: int


class CategorySummary(BaseModel):
    category: str
    count: int
    units: int
    expense: float


class SupplierSummary(BaseModel):
    supplier: str
    count: int
    units: int
    expense: float


class MonthlyExpenseSummary(BaseModel):
    month: str
    amount: float


class DashboardAnalyticsResponse(BaseModel):
    stats: InventoryStatsResponse
    categories: List[CategorySummary]
    suppliers: List[SupplierSummary]
    monthly_expenses: List[MonthlyExpenseSummary]
    top_expenses: List[Dict[str, Any]]
    top_required: List[Dict[str, Any]]
    recent_procurements: List[Dict[str, Any]]
    recent_expenses: List[Dict[str, Any]]
    low_stock_items: List[Dict[str, Any]]
