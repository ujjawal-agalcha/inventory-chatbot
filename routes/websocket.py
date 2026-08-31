import logging
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from database.models import SessionLocal
from services.auth_service import authenticate_websocket
from services.chat_service import handle_chat_websocket

logger = logging.getLogger("routes.websocket")

router = APIRouter(tags=["WebSocket Chatbot"])


@router.websocket("/ws/chat")
async def chat_websocket_endpoint(websocket: WebSocket):
    db = SessionLocal()
    try:
        user = authenticate_websocket(websocket, db)
        if not user:
            logger.warning("[WS] Unauthenticated connection rejected.")
            await websocket.accept()
            await websocket.send_json({
                "type": "error",
                "message": "Authentication required. Please log in.",
            })
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await handle_chat_websocket(websocket, user, db)

    except WebSocketDisconnect:
        logger.info("[WS] WebSocket client disconnected cleanly.")
    except Exception as exc:
        logger.error("[WS] WebSocket unhandled error: %s", repr(exc))
    finally:
        db.close()
