import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from database.models import Conversation, Message
from database.mongodb import get_conversations_collection, get_messages_collection

logger = logging.getLogger("database.repositories.conversation")


def list_conversations_repo(db: Session, user_id: str) -> List[Conversation]:
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


def get_conversation_repo(db: Session, conversation_id: str, user_id: str) -> Optional[Conversation]:
    return (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        .first()
    )


def create_conversation_repo(db: Session, user_id: str, title: str = "New Conversation") -> Conversation:
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

    return conv


def update_conversation_title_repo(
    db: Session,
    conversation_id: str,
    user_id: str,
    title: str,
) -> Optional[Conversation]:
    conv = get_conversation_repo(db, conversation_id, user_id)
    if not conv:
        return None
    conv.title = title.strip() or conv.title
    conv.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(conv)

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


def delete_conversation_repo(db: Session, conversation_id: str, user_id: str) -> bool:
    conv = get_conversation_repo(db, conversation_id, user_id)
    if not conv:
        return False
    db.delete(conv)
    db.commit()

    try:
        conv_col = get_conversations_collection()
        msg_col = get_messages_collection()
        conv_col.delete_one({"id": conversation_id})
        msg_col.delete_many({"conversation_id": conversation_id})
    except Exception as exc:
        logger.warning("MongoDB conversation delete warning: %s", exc)

    return True


def add_message_repo(
    db: Session,
    conversation_id: str,
    role: str,
    content: str,
    extra_data: str | dict | list | None = None,
) -> Message:
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

    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conv:
        conv.updated_at = datetime.utcnow()
        if role == "user" and (conv.title == "New Conversation" or not conv.title):
            short_title = content.strip()[:35]
            if len(content.strip()) > 35:
                short_title += "..."
            conv.title = short_title

    db.commit()
    db.refresh(msg)

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


def get_conversation_messages_repo(
    db: Session,
    conversation_id: str,
    limit: int = 100,
) -> List[Message]:
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
        .all()
    )
