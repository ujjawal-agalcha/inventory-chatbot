import json
import logging
from typing import Optional, List, Dict, Any
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from database.models import Conversation, Message
from database.repositories.conversation_repository import (
    list_conversations_repo,
    get_conversation_repo,
    create_conversation_repo,
    update_conversation_title_repo,
    delete_conversation_repo,
    add_message_repo,
    get_conversation_messages_repo,
)

logger = logging.getLogger("services.conversation")


def list_conversations(db: Session, user_id: str) -> List[Conversation]:
    """Retrieve all conversations for a specific user ordered by last update."""
    return list_conversations_repo(db, user_id)


def get_conversation(
    db: Session,
    conversation_id: str,
    user_id: str,
) -> Optional[Conversation]:
    """Retrieve a specific conversation verifying ownership."""
    return get_conversation_repo(db, conversation_id, user_id)


def create_conversation(
    db: Session,
    user_id: str,
    title: str = "New Conversation",
) -> Conversation:
    """Create a new persistent conversation for a user."""
    return create_conversation_repo(db, user_id, title)


def update_conversation_title(
    db: Session,
    conversation_id: str,
    user_id: str,
    title: str,
) -> Optional[Conversation]:
    """Update conversation title."""
    return update_conversation_title_repo(db, conversation_id, user_id, title)


def delete_conversation(
    db: Session,
    conversation_id: str,
    user_id: str,
) -> bool:
    """Delete a conversation and all its messages."""
    return delete_conversation_repo(db, conversation_id, user_id)


def add_message(
    db: Session,
    conversation_id: str,
    role: str,
    content: str,
    extra_data: str | dict | list | None = None,
) -> Message:
    """Add a message to a conversation."""
    return add_message_repo(db, conversation_id, role, content, extra_data)


def get_conversation_messages(
    db: Session,
    conversation_id: str,
    limit: int = 100,
) -> List[Message]:
    """Retrieve message history for a conversation."""
    return get_conversation_messages_repo(db, conversation_id, limit)


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
