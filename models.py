import uuid
import logging
from datetime import datetime
# pyrefly: ignore [missing-import]
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
)
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from config import DATABASE_URL, DATABASE_PATH

logger = logging.getLogger("database")
logger.info("Using database: %s", DATABASE_PATH)

# ============================================================
# DATABASE CONFIGURATION
# ============================================================

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


# ============================================================
# USER MODEL
# ============================================================

class User(Base):
    __tablename__ = "users"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )

    username = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
    )

    email = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
    )

    hashed_password = Column(
        String,
        nullable=False,
    )

    name = Column(
        String,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    # Relationships
    conversations = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )


# ============================================================
# CONVERSATION MODEL
# ============================================================

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )

    user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    title = Column(
        String,
        nullable=False,
        default="New Conversation",
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    user = relationship(
        "User",
        back_populates="conversations",
    )

    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


# ============================================================
# MESSAGE MODEL
# ============================================================

class Message(Base):
    __tablename__ = "messages"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )

    conversation_id = Column(
        String,
        ForeignKey("conversations.id"),
        nullable=False,
        index=True,
    )

    role = Column(
        String,
        nullable=False,  # "user", "assistant", "system"
    )

    content = Column(
        Text,
        nullable=False,
    )

    extra_data = Column(
        Text,
        nullable=True,  # JSON string with component / inventory payload
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    # Relationship
    conversation = relationship(
        "Conversation",
        back_populates="messages",
    )


# ============================================================
# INVENTORY MODEL
# ============================================================

class InventoryItem(Base):
    __tablename__ = "inventory"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    name = Column(
        String,
        nullable=False,
        index=True,
    )

    category = Column(
        String,
        nullable=False,
        index=True,
    )

    stock = Column(
        Integer,
        nullable=False,
        default=0,
    )

    min_stock = Column(
        Integer,
        nullable=False,
        default=0,
    )

    supplier = Column(
        String,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationship with reorder requests
    reorder_requests = relationship(
        "ReorderRequest",
        back_populates="item",
        cascade="all, delete-orphan",
    )


# ============================================================
# REORDER REQUEST MODEL
# ============================================================

class ReorderRequest(Base):
    __tablename__ = "reorder_requests"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    item_id = Column(
        Integer,
        ForeignKey("inventory.id"),
        nullable=False,
    )

    quantity = Column(
        Integer,
        nullable=False,
    )

    supplier = Column(
        String,
        nullable=False,
    )

    status = Column(
        String,
        nullable=False,
        default="Pending",
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    # Relationship back to inventory item
    item = relationship(
        "InventoryItem",
        back_populates="reorder_requests",
    )


# ============================================================
# CREATE DATABASE TABLES
# ============================================================

def init_models():
    Base.metadata.create_all(bind=engine)

init_models()


# ============================================================
# DATABASE DEPENDENCY
# ============================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
