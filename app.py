from __future__ import annotations

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from models import get_db
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
from ai_service import answer_question, KB
from config import SESSION_SECRET, DEV_AUTH_BYPASS, AUTHENTIK_BASE_URL
from auth import oauth


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="AI Inventory Management System",
    description="Inventory APIs + live inventory-aware RAG chatbot",
    version="2.0.1",
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    max_age=60 * 60 * 8,
    same_site="lax",
    https_only=False,
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ============================================================
# REQUEST MODELS
# ============================================================

class ReorderRequestBody(BaseModel):
    item_id: int
    quantity: int = Field(gt=0)


class StockUpdateBody(BaseModel):
    stock: int = Field(ge=0)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None


# ============================================================
# SERIALIZERS
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
            if item.updated_at
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
# AUTH
# ============================================================

def current_user(request: Request):
    if DEV_AUTH_BYPASS:
        return {
            "name": "Development User",
            "email": "dev@localhost",
            "username": "developer",
        }

    return request.session.get("user")


def require_user(request: Request):
    user = current_user(request)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required."
        )

    return user


# ============================================================
# PAGES
# ============================================================

@app.get("/")
async def root(request: Request):
    return RedirectResponse(
        "/chat" if current_user(request) else "/login",
        status_code=303,
    )


@app.get("/login")
async def login(request: Request):
    if DEV_AUTH_BYPASS:
        return RedirectResponse("/chat", status_code=303)

    if (
        not AUTHENTIK_BASE_URL
        or oauth is None
        or not hasattr(oauth, "authentik")
    ):
        raise HTTPException(
            503,
            "Authentik is not configured."
        )

    redirect_uri = request.url_for("auth_callback")

    return await oauth.authentik.authorize_redirect(
        request,
        redirect_uri,
    )


@app.get("/auth/callback")
async def auth_callback(request: Request):
    if DEV_AUTH_BYPASS:
        return RedirectResponse("/chat", status_code=303)

    if oauth is None or not hasattr(oauth, "authentik"):
        raise HTTPException(
            503,
            "Authentik is not configured."
        )

    try:
        token = await oauth.authentik.authorize_access_token(request)

        userinfo = (
            token.get("userinfo")
            or await oauth.authentik.userinfo(token=token)
        )

        request.session["user"] = {
            "name": (
                userinfo.get("name")
                or userinfo.get("preferred_username")
                or userinfo.get("email")
                or "User"
            ),
            "email": userinfo.get("email", ""),
            "username": userinfo.get("preferred_username", ""),
        }

        return RedirectResponse(
            "/chat",
            status_code=303,
        )

    except Exception as exc:
        raise HTTPException(
            400,
            f"Authentication failed: {exc}"
        )


@app.get("/chat", response_class=HTMLResponse)
async def chat(
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request)

    if not user:
        return RedirectResponse(
            "/login",
            status_code=303,
        )

    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={
            "user": user,
            "stats": get_inventory_stats(db),
        },
    )


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()

    return RedirectResponse(
        "/login",
        status_code=303,
    )


# ============================================================
# INVENTORY APIs
# ============================================================

@app.get("/api/inventory")
def inventory(
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    return [
        inventory_to_dict(i)
        for i in get_all_inventory(db)
    ]


@app.get("/api/inventory/low-stock")
def low_stock(
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    return [
        inventory_to_dict(i)
        for i in get_low_stock_items(db)
    ]


@app.get("/api/inventory/stats")
def inventory_stats(
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    return get_inventory_stats(db)


@app.get("/api/inventory/component/{name}")
def component(
    name: str,
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    item = get_component(db, name)

    if not item:
        raise HTTPException(
            404,
            f"Component '{name}' not found."
        )

    return inventory_to_dict(item)


@app.get("/api/component")
def component_by_query(
    name: str,
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    item = get_component(db, name)

    if not item:
        raise HTTPException(
            404,
            f"Component '{name}' not found."
        )

    return inventory_to_dict(item)


@app.get("/api/components")
def components_by_category(
    category: str,
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    items = [
        i
        for i in get_all_inventory(db)
        if i.category
        and i.category.lower() == category.strip().lower()
    ]

    return [
        inventory_to_dict(i)
        for i in items
    ]


@app.get("/api/inventory/search")
def inventory_search(
    q: str,
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    if not q.strip():
        raise HTTPException(
            400,
            "Search query cannot be empty."
        )

    return [
        inventory_to_dict(i)
        for i in search_inventory(db, q)
    ]


@app.put("/api/inventory/{item_id}/stock")
def change_stock(
    item_id: int,
    data: StockUpdateBody,
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    try:
        item = update_stock(
            db,
            item_id,
            data.stock,
        )

    except ValueError as exc:
        raise HTTPException(
            400,
            str(exc)
        )

    if not item:
        raise HTTPException(
            404,
            "Inventory item not found."
        )

    return {
        "message": "Stock updated successfully.",
        "item": inventory_to_dict(item),
    }


# ============================================================
# REORDER APIs
# ============================================================

@app.post("/api/reorders")
def reorder(
    data: ReorderRequestBody,
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    try:
        record = create_reorder_request(
            db,
            data.item_id,
            data.quantity,
        )

    except ValueError as exc:
        raise HTTPException(
            400,
            str(exc)
        )

    if not record:
        raise HTTPException(
            404,
            "Inventory item not found."
        )

    return {
        **reorder_to_dict(record),
        "message": "Reorder request created successfully.",
    }


@app.get("/api/reorders")
def reorders(
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    return [
        reorder_to_dict(r)
        for r in get_reorder_requests(db)
    ]


# ============================================================
# CHAT ROUTING HELPERS
# ============================================================

def is_greeting(message: str) -> bool:
    """
    Detect simple conversational greetings.
    These should NOT trigger inventory search or RAG.
    """

    text = message.strip().lower()

    greetings = {
        "hi",
        "hello",
        "hey",
        "hii",
        "hiii",
        "good morning",
        "good afternoon",
        "good evening",
        "good night",
        "hey there",
        "hello there",
    }

    return text in greetings


def is_thanks(message: str) -> bool:
    text = message.strip().lower()

    return text in {
        "thanks",
        "thank you",
        "thankyou",
        "thx",
        "ty",
    }


def is_goodbye(message: str) -> bool:
    text = message.strip().lower()

    return text in {
        "bye",
        "goodbye",
        "see you",
        "see ya",
        "talk to you later",
    }


def is_inventory_question(message: str) -> bool:
    """
    Determines whether the user is asking for LIVE inventory data.

    Knowledge/general questions should not enter this route.
    """

    low = message.lower()

    inventory_keywords = [
        "stock",
        "stocks",
        "available",
        "availability",
        "how many",
        "quantity",
        "units",
        "units left",
        "in inventory",
        "inventory",
        "low stock",
        "low-stock",
        "out of stock",
        "reorder",
        "re-order",
        "warehouse",
    ]

    return any(
        keyword in low
        for keyword in inventory_keywords
    )


def build_live_inventory_context(
    message: str,
    db: Session,
) -> tuple[str, list]:
    """
    Retrieve LIVE inventory information only when
    the user is actually asking an inventory question.
    """

    if not is_inventory_question(message):
        return "", []

    low = message.lower()

    all_items = get_all_inventory(db)

    # --------------------------------------------------------
    # 1. Exact product name matching
    # --------------------------------------------------------

    exact_matches = [
        item
        for item in all_items
        if item.name
        and item.name.lower() in low
    ]

    if exact_matches:
        items = exact_matches

    # --------------------------------------------------------
    # 2. Low-stock query
    # --------------------------------------------------------

    elif any(
        phrase in low
        for phrase in [
            "low stock",
            "low-stock",
            "shortage",
            "running low",
        ]
    ):
        items = get_low_stock_items(db)

    # --------------------------------------------------------
    # 3. Out-of-stock query
    # --------------------------------------------------------

    elif "out of stock" in low:
        items = [
            item
            for item in all_items
            if item.stock == 0
        ]

    # --------------------------------------------------------
    # 4. General inventory search
    # --------------------------------------------------------

    else:
        items = search_inventory(
            db,
            message,
        )[:10]

    # --------------------------------------------------------
    # Build context for the LLM
    # --------------------------------------------------------

    context = "\n".join(
        (
            f"- {i.name} | "
            f"category={i.category} | "
            f"stock={i.stock} | "
            f"minimum={i.min_stock} | "
            f"supplier={i.supplier}"
        )
        for i in items
    )

    return context, items


# ============================================================
# CHAT API
# ============================================================

@app.post("/api/chat")
def chat_api(
    data: ChatRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    message = data.message.strip()

    # ========================================================
    # 1. BASIC CONVERSATION
    # ========================================================

    if is_greeting(message):
        return {
            "type": "ai",
            "answer": (
                "Hey! 👋 I'm your inventory assistant. "
                "I can help you with products, IoT hardware, "
                "stock availability, and inventory information. "
                "What can I help you with?"
            ),
            "data": [],
            "sources": [],
            "mode": "conversation",
        }

    if is_thanks(message):
        return {
            "type": "ai",
            "answer": (
                "You're welcome! 😊 "
                "Let me know if you need anything else."
            ),
            "data": [],
            "sources": [],
            "mode": "conversation",
        }

    if is_goodbye(message):
        return {
            "type": "ai",
            "answer": (
                "Goodbye! 👋 "
                "Feel free to come back whenever you need help."
            ),
            "data": [],
            "sources": [],
            "mode": "conversation",
        }

    # ========================================================
    # 2. LIVE INVENTORY CONTEXT
    # ========================================================

    live_context, matched = build_live_inventory_context(
        message,
        db,
    )

    low = message.lower()

    # ========================================================
    # 3. LOW STOCK
    # ========================================================

    if any(
        x in low
        for x in [
            "low stock",
            "low-stock",
            "shortage",
            "running low",
        ]
    ):
        items = get_low_stock_items(db)

        if not items:
            answer = (
                "Good news — there are currently "
                "no products below their minimum "
                "stock level."
            )
        else:
            answer = (
                f"There are currently {len(items)} "
                f"product(s) below their minimum stock level."
            )

        return {
            "type": "inventory",
            "answer": answer,
            "data": [
                inventory_to_dict(i)
                for i in items
            ],
            "sources": ["live_inventory"],
            "mode": "live_inventory",
        }

    # ========================================================
    # 4. ALL INVENTORY
    # ========================================================

    if any(
        x in low
        for x in [
            "all inventory",
            "all products",
            "all components",
            "everything in inventory",
        ]
    ):
        items = get_all_inventory(db)

        return {
            "type": "inventory",
            "answer": (
                f"There are {len(items)} "
                f"products in the inventory."
            ),
            "data": [
                inventory_to_dict(i)
                for i in items
            ],
            "sources": ["live_inventory"],
            "mode": "live_inventory",
        }

    # ========================================================
    # 5. SPECIFIC STOCK QUESTION
    # ========================================================

    if (
        matched
        and any(
            x in low
            for x in [
                "stock",
                "available",
                "availability",
                "how many",
                "quantity",
                "units left",
            ]
        )
    ):
        # Use exact product match when available.
        item = matched[0]

        is_low = item.stock <= item.min_stock

        if item.stock == 0:
            availability = "currently out of stock"
        else:
            availability = (
                f"{item.stock} units available"
            )

        if item.stock == 0:
            status = "It needs to be reordered."
        elif is_low:
            status = (
                "It is currently below the "
                "minimum stock threshold."
            )
        else:
            status = (
                "It is currently above the "
                "minimum stock threshold."
            )

        answer = (
            f"We currently have {item.stock} "
            f"{item.name} unit(s) in stock. "
            f"The minimum stock level is "
            f"{item.min_stock} units. "
            f"{status}"
        )

        return {
            "type": "inventory",
            "answer": answer,
            "data": [
                inventory_to_dict(item)
            ],
            "sources": ["live_inventory"],
            "mode": "live_inventory",
        }

    # ========================================================
    # 6. GENERAL / KNOWLEDGE / COMPANY QUESTIONS
    # ========================================================

    # These go to the AI service.
    #
    # Important:
    # answer_question() is responsible for deciding whether
    # RAG/company knowledge is needed.
    #
    # Inventory data is NOT automatically attached here.

    result = answer_question(
        message,
        inventory_context=live_context,
    )

    result["type"] = "ai"

    # Never display inventory cards for normal AI answers.
    result["data"] = []

    return result


# ============================================================
# RAG
# ============================================================

@app.post("/api/rag/reload")
def reload_rag(
    _user=Depends(require_user),
):
    KB.reload()

    return {
        "message": "Knowledge base reloaded.",
        "chunks": len(KB.chunks),
    }


@app.get("/api/rag/search")
def rag_search(
    q: str,
    _user=Depends(require_user),
):
    if not q.strip():
        raise HTTPException(
            400,
            "Query cannot be empty."
        )

    return KB.search(q)


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "ai-inventory-management-system",
        "rag_chunks": len(KB.chunks),
    }
#python -m uvicorn app:app --reload --port 8001