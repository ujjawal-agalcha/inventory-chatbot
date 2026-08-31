import logging
from typing import Optional
# pyrefly: ignore [missing-import]
import pymongo
# pyrefly: ignore [missing-import]
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from config import MONGODB_URI, MONGODB_DATABASE

logger = logging.getLogger("database.mongodb")

_client: Optional[pymongo.MongoClient] = None
_db = None
_is_mock = False


def get_mongo_client() -> pymongo.MongoClient:
    """
    Get or create the singleton MongoDB client.
    Attempts live MongoDB connection first; if unreachable, falls back to mongomock.
    """
    global _client, _db, _is_mock

    if _client is not None:
        return _client

    try:
        logger.info("Attempting connection to MongoDB at %s...", MONGODB_URI)
        client = pymongo.MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=2500,
            connectTimeoutMS=2500,
            maxPoolSize=50,
        )
        # Verify connection
        client.admin.command("ping")
        _client = client
        _db = _client[MONGODB_DATABASE]
        _is_mock = False
        logger.info("Successfully connected to live MongoDB database: %s", MONGODB_DATABASE)
    except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as exc:
        logger.warning(
            "Could not connect to live MongoDB at %s (%s). Initializing in-memory MongoMock fallback.",
            MONGODB_URI,
            str(exc),
        )
        try:
            # pyrefly: ignore [missing-import]
            import mongomock
            _client = mongomock.MongoClient()
            _db = _client[MONGODB_DATABASE]
            _is_mock = True
            logger.info("MongoMock database initialized for '%s'.", MONGODB_DATABASE)
        except Exception as mock_err:
            logger.error("Failed to initialize MongoMock: %s", mock_err)
            raise exc

    return _client


def get_mongo_db():
    """Get the active MongoDB database instance."""
    if _db is None:
        get_mongo_client()
    return _db


def get_products_collection():
    return get_mongo_db()["products"]


def get_procurement_collection():
    return get_mongo_db()["procurement_records"]


def get_expenses_collection():
    return get_mongo_db()["expense_records"]


def get_imports_collection():
    return get_mongo_db()["import_history"]


def get_conversations_collection():
    return get_mongo_db()["conversations"]


def get_messages_collection():
    return get_mongo_db()["messages"]


def init_mongo_indexes():
    """
    Create unique and search indexes on MongoDB collections.
    """
    db = get_mongo_db()
    products = db["products"]
    procurement = db["procurement_records"]
    expenses = db["expense_records"]
    imports = db["import_history"]
    conversations = db["conversations"]
    messages = db["messages"]

    try:
        # Unique index on normalized_name to prevent duplicate products
        products.create_index("normalized_name", unique=True)
        products.create_index("category")
        products.create_index("sub_category")
        products.create_index("supplier")
        products.create_index("status")
        
        # Text index for search
        if not _is_mock:
            products.create_index([
                ("name", pymongo.TEXT),
                ("keywords", pymongo.TEXT),
                ("aliases", pymongo.TEXT),
                ("details", pymongo.TEXT),
                ("category", pymongo.TEXT),
            ])

        # Dedup index on row_hash
        procurement.create_index("row_hash")
        procurement.create_index("product_id")
        procurement.create_index("order_status")

        expenses.create_index("row_hash")
        expenses.create_index("product_id")
        expenses.create_index("expense_month")

        imports.create_index([("upload_timestamp", pymongo.DESCENDING)])

        # Conversation indexes
        conversations.create_index([("user_id", pymongo.ASCENDING), ("updated_at", pymongo.DESCENDING)])
        conversations.create_index("id", unique=True)
        messages.create_index([("conversation_id", pymongo.ASCENDING), ("created_at", pymongo.ASCENDING)])
        messages.create_index("id", unique=True)

        logger.info("MongoDB indexes initialized successfully.")
    except Exception as e:
        logger.warning("Error creating MongoDB indexes (mock or already exists): %s", e)


def is_mock_mode() -> bool:
    return _is_mock


def check_mongo_health() -> dict:
    """Return MongoDB connection status and statistics."""
    try:
        db = get_mongo_db()
        stats = {
            "status": "connected",
            "mode": "in-memory (mongomock)" if _is_mock else "live MongoDB",
            "database": MONGODB_DATABASE,
            "uri": MONGODB_URI if not _is_mock else "in-memory",
            "products_count": db["products"].count_documents({}),
            "procurement_count": db["procurement_records"].count_documents({}),
            "expenses_count": db["expense_records"].count_documents({}),
            "imports_count": db["import_history"].count_documents({}),
        }
        return stats
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "mode": "disconnected",
        }
