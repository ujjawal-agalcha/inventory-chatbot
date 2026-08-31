import logging
from contextlib import asynccontextmanager

# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from fastapi.staticfiles import StaticFiles
# pyrefly: ignore [missing-import]
from starlette.middleware.sessions import SessionMiddleware

from config import STATIC_DIR, DATABASE_PATH, SESSION_SECRET_KEY
from database.models import init_models
from database.mongodb import init_mongo_indexes, check_mongo_health
from ai.embeddings import build_or_refresh_index
from services.inventory_service import ensure_permanent_electronic_inventory
from routes import api_router

# ============================================================
# LOGGING CONFIGURATION
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("inventory-chatbot")


# ============================================================
# APPLICATION LIFECYCLE (STARTUP & SHUTDOWN)
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing SQLite database models at %s...", DATABASE_PATH)
    init_models()

    logger.info("Checking and initializing MongoDB indexes...")
    init_mongo_indexes()
    mongo_status = check_mongo_health()
    logger.info("MongoDB status: %s", mongo_status)

    logger.info("Verifying permanent electronic equipment inventory...")
    ensure_permanent_electronic_inventory()

    logger.info("Building / refreshing FAISS vector index from knowledge documents...")
    build_or_refresh_index()

    logger.info("Inventory Management & AI Assistant System started successfully.")
    yield
    logger.info("Shutting down Inventory Management & AI Assistant System...")


# ============================================================
# FASTAPI APP INSTANCE
# ============================================================
app = FastAPI(
    title="Inventory Management & AI Assistant System",
    description="Production-ready FastAPI + MongoDB + LangChain Gemini Chatbot with Excel Ingestion & Real-Time Analytics",
    version="2.0.0",
    lifespan=lifespan,
)


# ============================================================
# MIDDLEWARE
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
)


# ============================================================
# STATIC FILES MOUNT
# ============================================================
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ============================================================
# REGISTER ROUTERS
# ============================================================
app.include_router(api_router)


if __name__ == "__main__":
    # pyrefly: ignore [missing-import]
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8001, reload=True)