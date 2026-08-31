from typing import Optional, List, Any
from pydantic import BaseModel


class CreateConversationRequest(BaseModel):
    title: Optional[str] = "New Conversation"


class UpdateConversationRequest(BaseModel):
    title: str


class ConversationResponse(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: int = 0


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    extra_data: Optional[Any] = None
    created_at: Optional[str] = None


class ConversationDetailResponse(BaseModel):
    conversation: ConversationResponse
    messages: List[MessageResponse]
