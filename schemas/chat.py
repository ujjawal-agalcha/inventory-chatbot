from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field


class ChatMessagePayload(BaseModel):
    type: str = "message"
    content: Optional[str] = None
    message: Optional[str] = None
    conversation_id: Optional[str] = None


class ChatTokenEvent(BaseModel):
    type: str = "token"
    conversation_id: Optional[str] = None
    content: str


class ChatDoneEvent(BaseModel):
    type: str = "done"
    conversation_id: Optional[str] = None
    message: str
    data: List[Any] = []
    data_type: str = "ai"
    sources: List[str] = ["master_inventory", "knowledge_base"]


class ChatErrorEvent(BaseModel):
    type: str = "error"
    conversation_id: Optional[str] = None
    message: str
