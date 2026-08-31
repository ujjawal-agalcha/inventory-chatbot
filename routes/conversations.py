import logging
from typing import List
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, status
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from database.models import get_db, User
from schemas.conversation import (
    CreateConversationRequest,
    UpdateConversationRequest,
    ConversationResponse,
    ConversationDetailResponse,
)
from services.auth_service import get_current_user
from services.conversation_service import (
    list_conversations,
    get_conversation,
    create_conversation,
    update_conversation_title,
    delete_conversation,
    get_conversation_messages,
    conversation_to_dict,
    message_to_dict,
)

logger = logging.getLogger("routes.conversations")

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


@router.get("", response_model=List[ConversationResponse])
def get_conversations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convs = list_conversations(db, user.id)
    return [conversation_to_dict(c) for c in convs]


@router.post("", response_model=ConversationResponse)
def create_new_conversation(
    data: CreateConversationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = create_conversation(db, user.id, data.title or "New Conversation")
    return conversation_to_dict(conv)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_single_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = get_conversation(db, conversation_id, user.id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found or unauthorized.")

    messages = get_conversation_messages(db, conversation_id)
    return {
        "conversation": conversation_to_dict(conv),
        "messages": [message_to_dict(m) for m in messages],
    }


@router.patch("/{conversation_id}", response_model=ConversationResponse)
def update_conversation(
    conversation_id: str,
    data: UpdateConversationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = update_conversation_title(db, conversation_id, user.id, data.title)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found or unauthorized.")
    return conversation_to_dict(conv)


@router.delete("/{conversation_id}")
def remove_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    success = delete_conversation(db, conversation_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found or unauthorized.")
    return {"message": "Conversation deleted successfully."}
