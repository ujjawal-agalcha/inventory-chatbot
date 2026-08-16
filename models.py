# pyrefly: ignore [missing-import]
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
)
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DATABASE_URL = "sqlite:///./inventory.db"

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

Base.metadata.create_all(
    bind=engine
)


# ============================================================
# DATABASE DEPENDENCY
# ============================================================

def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()