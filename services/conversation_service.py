import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from models import Conversation, Message
from mongo_db import get_conversations_collection, get_messages_collection

logger = logging.getLogger("conversation_service")


# ============================================================
# CONVERSATIONS MANAGEMENT (SQLITE + MONGODB PERSISTENCE)
# ============================================================

def list_conversations(db: Session, user_id: str) -> list[Conversation]:
    """Retrieve all conversations for a specific user ordered by last update."""
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


def get_conversation(
    db: Session,
    conversation_id: str,
    user_id: str,
) -> Conversation | None:
    """Retrieve a specific conversation verifying ownership."""
    return (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        .first()
    )


def create_conversation(
    db: Session,
    user_id: str,
    title: str = "New Conversation",
) -> Conversation:
    """Create a new persistent conversation for a user."""
    conv = Conversation(
        user_id=user_id,
        title=title.strip() or "New Conversation",
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    # Replicate to MongoDB
    try:
        col = get_conversations_collection()
        col.update_one(
            {"id": conv.id},
            {"$set": {
                "id": conv.id,
                "user_id": user_id,
                "title": conv.title,
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
            }},
            upsert=True,
        )
    except Exception as exc:
        logger.warning("MongoDB conversation sync warning: %s", exc)

    logger.info("Created conversation %s for user %s", conv.id, user_id)
    return conv


def update_conversation_title(
    db: Session,
    conversation_id: str,
    user_id: str,
    title: str,
) -> Conversation | None:
    """Update conversation title."""
    conv = get_conversation(db, conversation_id, user_id)
    if not conv:
        return None
    conv.title = title.strip() or conv.title
    conv.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(conv)

    # Replicate to MongoDB
    try:
        col = get_conversations_collection()
        col.update_one(
            {"id": conv.id},
            {"$set": {
                "title": conv.title,
                "updated_at": conv.updated_at,
            }}
        )
    except Exception as exc:
        logger.warning("MongoDB conversation update warning: %s", exc)

    return conv


def delete_conversation(
    db: Session,
    conversation_id: str,
    user_id: str,
) -> bool:
    """Delete a conversation and all its messages."""
    conv = get_conversation(db, conversation_id, user_id)
    if not conv:
        return False
    db.delete(conv)
    db.commit()

    # Replicate to MongoDB
    try:
        conv_col = get_conversations_collection()
        msg_col = get_messages_collection()
        conv_col.delete_one({"id": conversation_id})
        msg_col.delete_many({"conversation_id": conversation_id})
    except Exception as exc:
        logger.warning("MongoDB conversation delete warning: %s", exc)

    logger.info("Deleted conversation %s", conversation_id)
    return True


def add_message(
    db: Session,
    conversation_id: str,
    role: str,
    content: str,
    extra_data: str | dict | list | None = None,
) -> Message:
    """Add a message to a conversation."""
    if isinstance(extra_data, (dict, list)):
        extra_data_str = json.dumps(extra_data)
    else:
        extra_data_str = extra_data

    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        extra_data=extra_data_str,
    )
    db.add(msg)

    # Touch conversation updated_at
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conv:
        conv.updated_at = datetime.utcnow()
        # If it's the first user message and title is default, set title based on message
        if role == "user" and (conv.title == "New Conversation" or not conv.title):
            short_title = content.strip()[:35]
            if len(content.strip()) > 35:
                short_title += "..."
            conv.title = short_title

    db.commit()
    db.refresh(msg)

    # Replicate to MongoDB
    try:
        msg_col = get_messages_collection()
        msg_col.insert_one({
            "id": msg.id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "extra_data": extra_data if not isinstance(extra_data, str) else extra_data_str,
            "created_at": msg.created_at,
        })
        if conv:
            conv_col = get_conversations_collection()
            conv_col.update_one(
                {"id": conv.id},
                {"$set": {"updated_at": conv.updated_at, "title": conv.title}},
                upsert=True,
            )
    except Exception as exc:
        logger.warning("MongoDB message sync warning: %s", exc)

    return msg


def get_conversation_messages(
    db: Session,
    conversation_id: str,
    limit: int = 100,
) -> list[Message]:
    """Retrieve message history for a conversation."""
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
        .all()
    )


def conversation_to_dict(conv: Conversation) -> dict:
    """Serialize conversation object to dict."""
    return {
        "id": conv.id,
        "user_id": conv.user_id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        "message_count": len(conv.messages) if conv.messages else 0,
    }


def message_to_dict(msg: Message) -> dict:
    """Serialize message object to dict."""
    extra = None
    if msg.extra_data:
        try:
            extra = json.loads(msg.extra_data)
        except Exception:
            extra = msg.extra_data

    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "role": msg.role,
        "content": msg.content,
        "extra_data": extra,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }
