import os
import json
import logging
from typing import Optional
from pathlib import Path

# pyrefly: ignore [missing-import]
from fastapi import (
    FastAPI,
    Request,
    Response,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)

# pyrefly: ignore [missing-import]
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

# pyrefly: ignore [missing-import]
from fastapi.templating import Jinja2Templates

# pyrefly: ignore [missing-import]
from fastapi.staticfiles import StaticFiles

# pyrefly: ignore [missing-import]
from starlette.middleware.sessions import SessionMiddleware

# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

from config import (
    SESSION_SECRET,
    DATABASE_PATH,
)

from models import (
    get_db,
    SessionLocal,
    User,
    Conversation,
    Message,
)

from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_current_user_optional,
    get_user_from_token,
)

from services.inventory_service import (
    get_all_inventory,
    get_component,
    search_inventory,
    get_low_stock_items,
    get_inventory_stats,
    create_reorder_request,
    get_reorder_requests,
    update_stock,
)

from services.conversation_service import (
    list_conversations,
    get_conversation,
    create_conversation,
    update_conversation_title,
    delete_conversation,
    add_message,
    get_conversation_messages,
    conversation_to_dict,
    message_to_dict,
)

import agent_service


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger("app")

logging.basicConfig(
    level=logging.INFO,
    format="[%(name)s] %(message)s",
)

logger.info("Using database: %s", DATABASE_PATH)


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Inventory Management System",
    description="IoT Inventory Management & AI Assistant with WebSockets",
    version="2.0.0",
)


# ============================================================
# MIDDLEWARE & STATIC
# ============================================================

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="inventory_session",
    max_age=60 * 60 * 24,
    same_site="lax",
    https_only=False,
)


BASE_DIR = Path(__file__).resolve().parent


app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)


templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================

class UserRegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=4)
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=5, max_length=100)


class UserLoginRequest(BaseModel):
    username: str
    password: str


class CreateConversationRequest(BaseModel):
    title: Optional[str] = "New Conversation"


class UpdateConversationRequest(BaseModel):
    title: str


class ReorderRequestBody(BaseModel):
    item_id: int
    quantity: int = Field(
        gt=0,
        description="Quantity to reorder"
    )


class StockUpdateBody(BaseModel):
    stock: int = Field(
        ge=0,
        description="New stock quantity"
    )


# ============================================================
# SERIALIZATION HELPERS
# ============================================================

def inventory_to_dict(item):
    return {
        "id": item.id,
        "name": item.name,
        "category": item.category,
        "stock": item.stock,
        "min_stock": item.min_stock,
        "supplier": item.supplier,
        "last_updated": (
            item.updated_at.isoformat()
            if getattr(item, "updated_at", None)
            else None
        ),
    }


def reorder_to_dict(reorder):
    return {
        "id": reorder.id,
        "item_id": reorder.item_id,
        "item_name": (
            reorder.item.name
            if reorder.item
            else None
        ),
        "quantity": reorder.quantity,
        "supplier": reorder.supplier,
        "status": reorder.status,
        "created_at": (
            reorder.created_at.isoformat()
            if reorder.created_at
            else None
        ),
    }


# ============================================================
# AUTHENTICATION API ENDPOINTS
# ============================================================

@app.post("/api/auth/register")
def register_user(
    data: UserRegisterRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    username = data.username.strip().lower()
    email = data.email.strip().lower()

    existing_user = db.query(User).filter(
        (User.username == username)
        | (User.email == email)
    ).first()

    if existing_user:
        if existing_user.username == username:
            raise HTTPException(
                status_code=400,
                detail="Username is already taken.",
            )

        raise HTTPException(
            status_code=400,
            detail="Email is already registered.",
        )

    new_user = User(
        username=username,
        email=email,
        name=data.name.strip(),
        hashed_password=hash_password(data.password),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token({
        "sub": new_user.id,
        "username": new_user.username,
        "name": new_user.name,
    })

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=False,
        max_age=60 * 60 * 24,
        samesite="lax",
    )

    request.session["user"] = {
        "id": new_user.id,
        "username": new_user.username,
        "name": new_user.name,
        "email": new_user.email,
    }

    return {
        "token": token,
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "name": new_user.name,
            "email": new_user.email,
        },
    }


@app.post("/api/auth/login")
def login_user(
    data: UserLoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    login_id = data.username.strip().lower()

    user = db.query(User).filter(
        (User.username == login_id)
        | (User.email == login_id)
    ).first()

    if not user or not verify_password(
        data.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password.",
        )

    token = create_access_token({
        "sub": user.id,
        "username": user.username,
        "name": user.name,
    })

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=False,
        max_age=60 * 60 * 24,
        samesite="lax",
    )

    request.session["user"] = {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "email": user.email,
    }

    return {
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "name": user.name,
            "email": user.email,
        },
    }


@app.get("/api/auth/me")
def get_me(
    user: User = Depends(get_current_user),
):
    return {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "email": user.email,
    }


# ============================================================
# WEB PAGES
# ============================================================

@app.get("/")
def root(
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user_optional(request, db)

    if user:
        return RedirectResponse(
            url="/chat",
            status_code=303,
        )

    return RedirectResponse(
        url="/login",
        status_code=303,
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user_optional(request, db)

    if user:
        return RedirectResponse(
            url="/chat",
            status_code=303,
        )

    # IMPORTANT:
    # New Starlette/FastAPI template syntax
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
        },
    )


@app.get("/logout")
def logout(
    response: Response,
    request: Request,
):
    request.session.clear()

    resp = RedirectResponse(
        url="/login",
        status_code=303,
    )

    resp.delete_cookie("access_token")
    resp.delete_cookie("inventory_session")

    return resp


@app.get("/chat", response_class=HTMLResponse)
def chat_page(
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user_optional(request, db)

    # --------------------------------------------------------
    # Create default admin if no admin exists
    # --------------------------------------------------------

    if not user:
        default_admin = (
            db.query(User)
            .filter(User.username == "admin")
            .first()
        )

        if not default_admin:
            default_admin = User(
                username="admin",
                email="admin@inventory.local",
                name="System Administrator",
                hashed_password=hash_password("admin123"),
            )

            db.add(default_admin)
            db.commit()
            db.refresh(default_admin)

        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    stats = get_inventory_stats(db)

    # IMPORTANT:
    # New Starlette/FastAPI template syntax
    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={
            "request": request,
            "user": user,
            "stats": stats,
        },
    )


# ============================================================
# CONVERSATION REST APIS
# ============================================================

@app.get("/api/conversations")
def get_conversations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convs = list_conversations(
        db,
        user.id,
    )

    return [
        conversation_to_dict(c)
        for c in convs
    ]


@app.post("/api/conversations")
def create_new_conversation(
    data: CreateConversationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = create_conversation(
        db,
        user.id,
        data.title or "New Conversation",
    )

    return conversation_to_dict(conv)


@app.get("/api/conversations/{conversation_id}")
def get_single_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = get_conversation(
        db,
        conversation_id,
        user.id,
    )

    if not conv:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found or unauthorized.",
        )

    messages = get_conversation_messages(
        db,
        conversation_id,
    )

    return {
        "conversation": conversation_to_dict(conv),
        "messages": [
            message_to_dict(m)
            for m in messages
        ],
    }


@app.patch("/api/conversations/{conversation_id}")
def update_conversation(
    conversation_id: str,
    data: UpdateConversationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = update_conversation_title(
        db,
        conversation_id,
        user.id,
        data.title,
    )

    if not conv:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found or unauthorized.",
        )

    return conversation_to_dict(conv)


@app.delete("/api/conversations/{conversation_id}")
def remove_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    success = delete_conversation(
        db,
        conversation_id,
        user.id,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found or unauthorized.",
        )

    return {
        "message": "Conversation deleted successfully."
    }


# ============================================================
# INVENTORY REST APIS
# ============================================================

@app.get("/api/inventory")
def inventory_list(
    db: Session = Depends(get_db),
):
    items = get_all_inventory(db)

    return [
        inventory_to_dict(item)
        for item in items
    ]


@app.get("/api/inventory/low-stock")
def low_stock(
    db: Session = Depends(get_db),
):
    items = get_low_stock_items(db)

    return [
        inventory_to_dict(item)
        for item in items
    ]


@app.get("/api/inventory/stats")
def inventory_stats(
    db: Session = Depends(get_db),
):
    return get_inventory_stats(db)


@app.get("/api/inventory/component/{name}")
def component_by_path(
    name: str,
    db: Session = Depends(get_db),
):
    item = get_component(
        db,
        name,
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail=f"Component '{name}' not found.",
        )

    return inventory_to_dict(item)


@app.get("/api/component")
def component_by_query(
    name: str,
    db: Session = Depends(get_db),
):
    if not name.strip():
        raise HTTPException(
            status_code=400,
            detail="Component name cannot be empty.",
        )

    item = get_component(
        db,
        name,
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail=f"Component '{name}' not found.",
        )

    return inventory_to_dict(item)


@app.get("/api/components")
def components_by_category(
    category: str,
    db: Session = Depends(get_db),
):
    if not category.strip():
        raise HTTPException(
            status_code=400,
            detail="Category cannot be empty.",
        )

    items = get_all_inventory(db)

    matching = [
        item
        for item in items
        if (
            item.category
            and item.category.lower()
            == category.strip().lower()
        )
    ]

    return [
        inventory_to_dict(item)
        for item in matching
    ]


@app.get("/api/inventory/search")
def inventory_search(
    q: str,
    db: Session = Depends(get_db),
):
    if not q.strip():
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty.",
        )

    items = search_inventory(
        db,
        q,
    )

    return [
        inventory_to_dict(item)
        for item in items
    ]


@app.put("/api/inventory/{item_id}/stock")
def change_stock(
    item_id: int,
    data: StockUpdateBody,
    db: Session = Depends(get_db),
):
    try:
        item = update_stock(
            db,
            item_id,
            data.stock,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Inventory item not found.",
        )

    return {
        "message": "Stock updated successfully.",
        "item": inventory_to_dict(item),
    }


@app.post("/api/reorders")
def create_reorder(
    data: ReorderRequestBody,
    db: Session = Depends(get_db),
):
    try:
        record = create_reorder_request(
            db=db,
            item_id=data.item_id,
            quantity=data.quantity,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Inventory item not found.",
        )

    return {
        **reorder_to_dict(record),
        "message": "Reorder request created successfully.",
    }


@app.get("/api/reorders")
def list_reorders(
    db: Session = Depends(get_db),
):
    records = get_reorder_requests(db)

    return [
        reorder_to_dict(record)
        for record in records
    ]


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "inventory-management-system",
        "database": str(DATABASE_PATH),
    }


# ============================================================
# WEBSOCKET CHATBOT
# ============================================================

@app.websocket("/ws/chat")
async def chat_websocket(
    websocket: WebSocket,
):
    db = SessionLocal()

    try:
        # ----------------------------------------------------
        # Authenticate user
        # ----------------------------------------------------

        token = (
            websocket.query_params.get("token")
            or websocket.cookies.get("access_token")
        )

        user = None

        if token:
            user = get_user_from_token(
                token,
                db,
            )

        # Fallback to session cookie
        if not user:
            session_cookie = websocket.cookies.get(
                "inventory_session"
            )

            if session_cookie:
                user = db.query(User).first()

        if not user:
            logger.warning(
                "[WS] Unauthenticated connection rejected."
            )

            await websocket.accept()

            await websocket.send_json({
                "type": "error",
                "message": (
                    "Authentication required. "
                    "Please log in."
                ),
            })

            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION
            )

            return

        await websocket.accept()

        logger.info(
            "[WS] Authenticated user connected: %s (%s)",
            user.username,
            user.id,
        )

        # ----------------------------------------------------
        # Active conversation
        # ----------------------------------------------------

        active_conversation_id = None

        # ----------------------------------------------------
        # WebSocket message loop
        # ----------------------------------------------------

        while True:

            raw_data = await websocket.receive_text()

            if not raw_data:
                continue

            try:
                data = json.loads(raw_data)

            except Exception:
                await websocket.send_json({
                    "type": "error",
                    "message": (
                        "Invalid JSON format received."
                    ),
                })

                continue

            msg_type = data.get(
                "type",
                "message",
            )

            # ------------------------------------------------
            # Ping / Pong
            # ------------------------------------------------

            if msg_type == "ping":
                await websocket.send_json({
                    "type": "pong"
                })
                continue

            # ------------------------------------------------
            # Initialize / load conversation
            # ------------------------------------------------

            if msg_type == "init":

                conv_id = data.get(
                    "conversation_id"
                )

                if conv_id:

                    conv = get_conversation(
                        db,
                        conv_id,
                        user.id,
                    )

                    if conv:
                        active_conversation_id = conv.id

                        await websocket.send_json({
                            "type": "conversation_loaded",
                            "conversation":
                                conversation_to_dict(conv),
                        })

                continue

            # ------------------------------------------------
            # Chat message
            # ------------------------------------------------

            if msg_type == "message":

                content = str(
                    data.get("content")
                    or data.get("message")
                    or ""
                ).strip()

                conv_id = (
                    data.get("conversation_id")
                    or active_conversation_id
                )

                if not content:
                    await websocket.send_json({
                        "type": "error",
                        "message": (
                            "Message cannot be empty."
                        ),
                    })

                    continue

                # --------------------------------------------
                # Find conversation
                # --------------------------------------------

                conversation = None

                if conv_id:
                    conversation = get_conversation(
                        db,
                        conv_id,
                        user.id,
                    )

                # --------------------------------------------
                # Create conversation automatically
                # --------------------------------------------

                if not conversation:

                    title = (
                        content[:30]
                        + (
                            "..."
                            if len(content) > 30
                            else ""
                        )
                    )

                    conversation = create_conversation(
                        db,
                        user.id,
                        title=title,
                    )

                    conv_id = conversation.id
                    active_conversation_id = conv_id

                    await websocket.send_json({
                        "type": "conversation_created",
                        "conversation":
                            conversation_to_dict(
                                conversation
                            ),
                    })

                # --------------------------------------------
                # Get conversation history
                # --------------------------------------------

                past_messages = (
                    get_conversation_messages(
                        db,
                        conv_id,
                        limit=20,
                    )
                )

                history = [
                    {
                        "role": m.role,
                        "content": m.content,
                    }
                    for m in past_messages
                ]

                # --------------------------------------------
                # Persist user message
                # --------------------------------------------

                add_message(
                    db,
                    conv_id,
                    role="user",
                    content=content,
                )

                # --------------------------------------------
                # Message start
                # --------------------------------------------

                await websocket.send_json({
                    "type": "message_start",
                    "conversation_id": conv_id,
                })

                # --------------------------------------------
                # Agent streaming
                # --------------------------------------------

                final_text = ""
                final_data = []
                final_data_type = "ai"

                try:

                    async for event in (
                        agent_service.stream_agent_response(
                            content,
                            history,
                            db,
                        )
                    ):

                        if event["type"] == "token":

                            token_str = event[
                                "content"
                            ]

                            final_text += token_str

                            await websocket.send_json({
                                "type": "token",
                                "conversation_id":
                                    conv_id,
                                "content": token_str,
                            })

                        elif event["type"] == "done":

                            final_text = event.get(
                                "message",
                                final_text,
                            )

                            final_data = event.get(
                                "data",
                                [],
                            )

                            final_data_type = event.get(
                                "data_type",
                                "ai",
                            )

                    # ----------------------------------------
                    # Persist assistant response
                    # ----------------------------------------

                    add_message(
                        db,
                        conv_id,
                        role="assistant",
                        content=final_text,
                        extra_data=final_data,
                    )

                    # ----------------------------------------
                    # Message end
                    # ----------------------------------------

                    await websocket.send_json({
                        "type": "message_end",
                        "conversation_id": conv_id,
                        "message": final_text,
                        "data": final_data,
                        "data_type": final_data_type,
                        "sources": [
                            "live_inventory",
                            "knowledge_base",
                        ],
                    })

                except Exception as stream_err:

                    logger.error(
                        "[WS STREAM ERROR] %s",
                        repr(stream_err),
                    )

                    await websocket.send_json({
                        "type": "error",
                        "conversation_id": conv_id,
                        "message": (
                            "An error occurred while "
                            "streaming the AI response."
                        ),
                    })

    except WebSocketDisconnect:

        logger.info(
            "[WS] Client disconnected."
        )

    except Exception as exc:

        logger.error(
            "[WS UNEXPECTED ERROR] %s",
            repr(exc),
        )

    finally:

        db.close() 

#python -m uvicorn app:app --reload --port 8001