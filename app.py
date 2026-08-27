import os
import json
import logging
from typing import Optional, List
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
    UploadFile,
    File,
    Form,
    status,
)
# pyrefly: ignore [missing-import]
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
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
    MONGODB_URI,
    MONGODB_DATABASE,
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

from mongo_db import check_mongo_health, init_mongo_indexes

from services.mongo_inventory_service import (
    get_all_products,
    get_product,
    search_products,
    get_low_stock_products,
    get_inventory_stats,
    get_dashboard_analytics,
    update_product_stock,
    create_reorder_request,
    get_all_reorders,
    get_import_history_list,
    ensure_permanent_electronic_inventory,
    preview_import_deletion,
    delete_import_batch,
    clean_legacy_sample_data,
)

from services.excel_import_service import (
    process_procurement_data,
    process_expenses_data,
    auto_detect_and_import,
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

logger.info("Using SQLite Auth Database: %s", DATABASE_PATH)
logger.info("Using MongoDB Inventory: %s (%s)", MONGODB_URI, MONGODB_DATABASE)

# Initialize MongoDB indexes and permanent electronic inventory on startup
try:
    init_mongo_indexes()
    ensure_permanent_electronic_inventory()
    logger.info("Permanent electronic inventory verified in MongoDB.")
except Exception as e:
    logger.warning("MongoDB initialization on startup: %s", e)


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Inventory Management & Procurement Intelligence System",
    description="Production Real-Data Inventory Management, Excel Imports & MongoDB-Backed AI Chatbot",
    version="3.0.0",
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
    item_id: str
    quantity: int = Field(gt=0, description="Quantity to reorder")
    vendor: Optional[str] = None
    remarks: Optional[str] = None


class StockUpdateBody(BaseModel):
    stock: int = Field(ge=0, description="New stock quantity")


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
        (User.username == username) | (User.email == email)
    ).first()

    if existing_user:
        if existing_user.username == username:
            raise HTTPException(status_code=400, detail="Username is already taken.")
        raise HTTPException(status_code=400, detail="Email is already registered.")

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
        (User.username == login_id) | (User.email == login_id)
    ).first()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

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
def get_me(user: User = Depends(get_current_user)):
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
def root(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if user:
        return RedirectResponse(url="/chat", status_code=303)
    return RedirectResponse(url="/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if user:
        return RedirectResponse(url="/chat", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"request": request},
    )


@app.get("/logout")
def logout(response: Response, request: Request):
    request.session.clear()
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie("access_token")
    resp.delete_cookie("inventory_session")
    return resp


@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)

    if not user:
        default_admin = db.query(User).filter(User.username == "admin").first()
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

        return RedirectResponse(url="/login", status_code=303)

    stats = get_inventory_stats()
    mongo_health = check_mongo_health()

    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={
            "request": request,
            "user": user,
            "stats": stats,
            "mongo_health": mongo_health,
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
    convs = list_conversations(db, user.id)
    return [conversation_to_dict(c) for c in convs]


@app.post("/api/conversations")
def create_new_conversation(
    data: CreateConversationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = create_conversation(db, user.id, data.title or "New Conversation")
    return conversation_to_dict(conv)


@app.get("/api/conversations/{conversation_id}")
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


@app.patch("/api/conversations/{conversation_id}")
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


@app.delete("/api/conversations/{conversation_id}")
def remove_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    success = delete_conversation(db, conversation_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found or unauthorized.")
    return {"message": "Conversation deleted successfully."}


# ============================================================
# MONGODB INVENTORY REST APIS
# ============================================================

@app.get("/api/inventory")
def inventory_list():
    """Retrieve all Master Inventory items from MongoDB."""
    return get_all_products()


@app.get("/api/inventory/low-stock")
def low_stock():
    """Retrieve low-stock inventory products from MongoDB."""
    return get_low_stock_products()


@app.get("/api/inventory/stats")
def inventory_stats():
    """Retrieve live inventory aggregates from MongoDB."""
    return get_inventory_stats()


@app.get("/api/dashboard/analytics")
def dashboard_analytics():
    """Comprehensive MongoDB analytics for the dashboard charts & tables."""
    return get_dashboard_analytics()


@app.get("/api/inventory/component/{name}")
def component_by_path(name: str):
    item = get_product(name)
    if not item:
        raise HTTPException(status_code=404, detail=f"Product '{name}' not found in MongoDB.")
    return item


@app.get("/api/component")
def component_by_query(name: str):
    if not name.strip():
        raise HTTPException(status_code=400, detail="Component name cannot be empty.")
    item = get_product(name)
    if not item:
        raise HTTPException(status_code=404, detail=f"Product '{name}' not found in MongoDB.")
    return item


@app.get("/api/components")
def components_by_category(category: str):
    if not category.strip():
        raise HTTPException(status_code=400, detail="Category cannot be empty.")
    return get_all_products(category=category.strip())


@app.get("/api/inventory/search")
def inventory_search(q: str):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")
    return search_products(q)


@app.put("/api/inventory/{item_id}/stock")
def change_stock(item_id: str, data: StockUpdateBody):
    try:
        item = update_product_stock(item_id, data.stock)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found.")

    return {
        "message": "Stock updated successfully in MongoDB.",
        "item": item,
    }


@app.post("/api/reorders")
def create_reorder(data: ReorderRequestBody):
    try:
        record = create_reorder_request(
            item_identifier=data.item_id,
            quantity=data.quantity,
            vendor=data.vendor,
            remarks=data.remarks,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if not record:
        raise HTTPException(status_code=404, detail="Product not found for reorder.")

    return {
        **record,
        "message": "Reorder request saved in MongoDB.",
    }


@app.get("/api/reorders")
def list_reorders():
    return get_all_reorders()


@app.get("/api/imports")
def list_imports():
    """Retrieve history of uploaded Excel files."""
    return get_import_history_list()


# ============================================================
# EXCEL UPLOAD REST APIS
# ============================================================

@app.post("/api/upload/procurement")
async def upload_procurement_excel(
    file: UploadFile = File(...),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Upload and import File 1: Procurement / Requirements Workbook.
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload an Excel (.xlsx or .xls) file.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    username = user.username if user else "admin"
    try:
        result = process_procurement_data(content, file.filename, uploaded_by=username)
        return {
            "success": True,
            "message": f"Procurement data from '{file.filename}' processed successfully.",
            "data": result,
        }
    except Exception as e:
        logger.exception("Failed to process procurement file: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


@app.post("/api/upload/expenses")
async def upload_expenses_excel(
    file: UploadFile = File(...),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Upload and import File 2: Master Procurement / Expenses Workbook.
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload an Excel (.xlsx or .xls) file.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    username = user.username if user else "admin"
    try:
        result = process_expenses_data(content, file.filename, uploaded_by=username)
        return {
            "success": True,
            "message": f"Expense data from '{file.filename}' processed successfully.",
            "data": result,
        }
    except Exception as e:
        logger.exception("Failed to process expenses file: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


@app.post("/api/upload/auto")
async def upload_auto_excel(
    file: UploadFile = File(...),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Intelligently detect whether file is Procurement or Expenses and import into MongoDB.
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload an Excel (.xlsx or .xls) file.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    username = user.username if user else "admin"
    try:
        result = auto_detect_and_import(content, file.filename, uploaded_by=username)
        return {
            "success": True,
            "message": f"Excel workbook '{file.filename}' auto-classified and imported successfully.",
            "data": result,
        }
    except Exception as e:
        logger.exception("Failed to auto-import file: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to import file: {str(e)}")


# ============================================================
# PROTECTED ADMIN CLEANUP REST APIS
# ============================================================

@app.get("/api/admin/imports/{import_id}/preview")
def preview_import_delete(
    import_id: str,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Admin endpoint to preview records that will be affected by deleting an import batch.
    """
    try:
        preview = preview_import_deletion(import_id)
        return preview
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error previewing import deletion: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to generate preview: {str(e)}")


@app.delete("/api/admin/imports/{import_id}")
def delete_import(
    import_id: str,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Protected Admin endpoint to safely delete an import batch:
    - Removes batch procurement and expense records
    - Removes products created exclusively by this import (source_type == 'excel_import')
    - Preserves legitimate electronic equipment inventory
    """
    try:
        result = delete_import_batch(import_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error deleting import batch: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to delete import batch: {str(e)}")


@app.post("/api/admin/cleanup-sample-data")
def cleanup_sample_data(
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Protected Admin endpoint to safely clean up any legacy sample Excel imports.
    Guarantees permanent electronic equipment data is preserved.
    """
    try:
        result = clean_legacy_sample_data()
        return result
    except Exception as e:
        logger.exception("Error cleaning sample data: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to clean sample data: {str(e)}")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "inventory-management-system",
        "sqlite_db": str(DATABASE_PATH),
        "mongodb": check_mongo_health(),
    }


# ============================================================
# WEBSOCKET CHATBOT (REAL-TIME STREAMING + MONGODB SOURCE OF TRUTH)
# ============================================================

@app.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    db = SessionLocal()

    try:
        # Authenticate user
        token = (
            websocket.query_params.get("token")
            or websocket.cookies.get("access_token")
        )

        user = None
        if token:
            user = get_user_from_token(token, db)

        if not user:
            session_cookie = websocket.cookies.get("inventory_session")
            if session_cookie:
                user = db.query(User).first()

        if not user:
            logger.warning("[WS] Unauthenticated connection rejected.")
            await websocket.accept()
            await websocket.send_json({
                "type": "error",
                "message": "Authentication required. Please log in.",
            })
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await websocket.accept()
        logger.info("[WS] Authenticated user connected: %s (%s)", user.username, user.id)

        active_conversation_id = None

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
                    async for event in agent_service.stream_agent_response(content, history, db):
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
                        "sources": ["live_mongodb_inventory", "knowledge_base"],
                    })

                except Exception as stream_err:
                    logger.error("[WS STREAM ERROR] %s", repr(stream_err))
                    await websocket.send_json({
                        "type": "error",
                        "conversation_id": conv_id,
                        "message": "An error occurred while streaming the AI response.",
                    })

    except WebSocketDisconnect:
        logger.info("[WS] Client disconnected.")
    except Exception as exc:
        logger.error("[WS UNEXPECTED ERROR] %s", repr(exc))
    finally:
        db.close()