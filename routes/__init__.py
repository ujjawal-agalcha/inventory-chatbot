# pyrefly: ignore [missing-import]
from fastapi import APIRouter

from .auth import router as auth_router
from .conversations import router as conversations_router
from .inventory import router as inventory_router
from .dashboard import router as dashboard_router
from .uploads import router as uploads_router
from .websocket import router as websocket_router

# Aggregator Router
api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(conversations_router)
api_router.include_router(inventory_router)
api_router.include_router(dashboard_router)
api_router.include_router(uploads_router)
api_router.include_router(websocket_router)
