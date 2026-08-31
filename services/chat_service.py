import json
import logging
from typing import Optional, List, Dict, Any
# pyrefly: ignore [missing-import]
from fastapi import WebSocket, WebSocketDisconnect, status
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from database.models import User
from services.conversation_service import (
    get_conversation,
    create_conversation,
    get_conversation_messages,
    add_message,
    conversation_to_dict,
)
from services.agent_service import stream_agent_response

logger = logging.getLogger("services.chat")


async def handle_chat_websocket(websocket: WebSocket, user: User, db: Session):
    """
    Handle live streaming chatbot WebSocket session for authenticated user.
    """
    await websocket.accept()
    logger.info("[WS] Authenticated user connected: %s (%s)", user.username, user.id)

    active_conversation_id = None

    try:
        while True:
            raw_data = await websocket.receive_text()
            if not raw_data:
                continue

            try:
                data = json.loads(raw_data)
            except Exception:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format received.",
                })
                continue

            msg_type = data.get("type", "message")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if msg_type == "init":
                conv_id = data.get("conversation_id")
                if conv_id:
                    conv = get_conversation(db, conv_id, user.id)
                    if conv:
                        active_conversation_id = conv.id
                        await websocket.send_json({
                            "type": "conversation_loaded",
                            "conversation": conversation_to_dict(conv),
                        })
                continue

            if msg_type == "message":
                content = str(data.get("content") or data.get("message") or "").strip()
                conv_id = data.get("conversation_id") or active_conversation_id

                if not content:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Message cannot be empty.",
                    })
                    continue

                # Find or create conversation
                conversation = None
                if conv_id:
                    conversation = get_conversation(db, conv_id, user.id)

                if not conversation:
                    title = content[:30] + ("..." if len(content) > 30 else "")
                    conversation = create_conversation(db, user.id, title=title)
                    conv_id = conversation.id
                    active_conversation_id = conv_id
                    await websocket.send_json({
                        "type": "conversation_created",
                        "conversation": conversation_to_dict(conversation),
                    })

                # Retrieve history for context
                past_messages = get_conversation_messages(db, conv_id, limit=20)
                history = [
                    {"role": m.role, "content": m.content}
                    for m in past_messages
                ]

                # Persist user message
                add_message(db, conv_id, role="user", content=content)

                # Send message start
                await websocket.send_json({
                    "type": "message_start",
                    "conversation_id": conv_id,
                })

                # Stream response from MongoDB-backed Agent
                final_text = ""
                final_data = []
                final_data_type = "ai"

                try:
                    async for event in stream_agent_response(content, history, db):
                        if event["type"] == "token":
                            token_str = event["content"]
                            final_text += token_str
                            await websocket.send_json({
                                "type": "token",
                                "conversation_id": conv_id,
                                "content": token_str,
                            })
                        elif event["type"] == "done":
                            final_text = event.get("message", final_text)
                            final_data = event.get("data", [])
                            final_data_type = event.get("data_type", "ai")

                    # Persist assistant response
                    add_message(
                        db,
                        conv_id,
                        role="assistant",
                        content=final_text,
                        extra_data=final_data,
                    )

                    # Send message end
                    await websocket.send_json({
                        "type": "message_end",
                        "conversation_id": conv_id,
                        "message": final_text,
                        "data": final_data,
                        "data_type": final_data_type,
                        "sources": ["master_inventory", "knowledge_base"],
                    })

                except Exception as stream_err:
                    logger.error("[WS STREAM ERROR] %s", repr(stream_err))
                    await websocket.send_json({
                        "type": "error",
                        "conversation_id": conv_id,
                        "message": "An error occurred while streaming the AI response.",
                    })

    except WebSocketDisconnect:
        logger.info("[WS] Client disconnected (%s).", user.username)
    except Exception as exc:
        logger.error("[WS UNEXPECTED ERROR] %s", repr(exc))
