from fastapi import (
    FastAPI,
    Request,
    Depends,
    HTTPException,
)

from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
)

from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from starlette.middleware.sessions import SessionMiddleware

from sqlalchemy.orm import Session

from pydantic import BaseModel, Field

from models import (
    get_db,
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

from auth import oauth
from config import SESSION_SECRET

import agent_service

# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Inventory Management System",
    description="Inventory Management API",
    version="1.0.0",
)


# ============================================================
# SESSION MIDDLEWARE
# ============================================================

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    max_age=60 * 60 * 8,
    same_site="lax",
    https_only=False,
)


# ============================================================
# STATIC FILES
# ============================================================

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)


# ============================================================
# TEMPLATES
# ============================================================

templates = Jinja2Templates(
    directory="templates"
)


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================

class ReorderRequestBody(BaseModel):

    item_id: int

    quantity: int = Field(
        gt=0,
        description="Quantity to reorder",
    )


class StockUpdateBody(BaseModel):

    stock: int = Field(
        ge=0,
        description="New stock quantity",
    )


class ChatRequest(BaseModel):

    message: str


# ============================================================
# HELPER: INVENTORY ITEM -> DICT
# ============================================================

def inventory_to_dict(item):

    return {
        "id": item.id,

        "name": item.name,

        "category": item.category,

        "stock": item.stock,

        "min_stock": item.min_stock,

        "supplier": item.supplier,

        # Frontend expects last_updated.
        # SQLAlchemy model uses updated_at.
        "last_updated": (
            item.updated_at.isoformat()
            if getattr(item, "updated_at", None)
            else None
        ),
    }


# ============================================================
# HELPER: REORDER -> DICT
# ============================================================

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
# ROOT
# ============================================================

@app.get("/")
async def root(request: Request):

    user = request.session.get("user")

    if user:

        return RedirectResponse(
            url="/chat",
            status_code=303,
        )

    return RedirectResponse(
        url="/login",
        status_code=303,
    )


# ============================================================
# LOGIN
# ============================================================

@app.get("/login")
async def login(request: Request):

    redirect_uri = request.url_for(
        "auth_callback"
    )

    return await oauth.authentik.authorize_redirect(
        request,
        redirect_uri,
    )


# ============================================================
# AUTHENTIK CALLBACK
# ============================================================

@app.get("/auth/callback")
async def auth_callback(request: Request):

    try:

        token = await oauth.authentik.authorize_access_token(
            request
        )

        userinfo = token.get("userinfo")

        if not userinfo:

            userinfo = await oauth.authentik.userinfo(
                token=token
            )

        user = {

            "name": (
                userinfo.get("name")
                or userinfo.get("preferred_username")
                or userinfo.get("email")
                or "User"
            ),

            "email": userinfo.get(
                "email",
                ""
            ),

            "username": userinfo.get(
                "preferred_username",
                ""
            ),
        }

        request.session["user"] = user

        return RedirectResponse(
            url="/chat",
            status_code=303,
        )

    except Exception as error:

        print(
            "Authentik callback error:",
            repr(error),
        )

        return HTMLResponse(
            content="""
            <html>
                <head>
                    <title>Authentication Error</title>
                </head>

                <body>
                    <h2>Authentication failed</h2>

                    <p>
                        Please close this page and try
                        logging in again.
                    </p>
                </body>
            </html>
            """,
            status_code=400,
        )


# ============================================================
# DASHBOARD
# ============================================================

@app.get(
    "/chat",
    response_class=HTMLResponse,
)
async def chat(
    request: Request,
    db: Session = Depends(get_db),
):

    user = request.session.get("user")

    if not user:

        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    stats = get_inventory_stats(db)

    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={
            "user": user,
            "stats": stats,
        },
    )


# ============================================================
# LOGOUT
# ============================================================

@app.get("/logout")
async def logout(request: Request):

    request.session.clear()

    return RedirectResponse(
        url="/login",
        status_code=303,
    )


# ============================================================
# GET ALL INVENTORY
# ============================================================

@app.get("/api/inventory")
def inventory(
    db: Session = Depends(get_db),
):

    items = get_all_inventory(db)

    return [
        inventory_to_dict(item)
        for item in items
    ]


# ============================================================
# GET LOW STOCK
# ============================================================

@app.get("/api/inventory/low-stock")
def low_stock(
    db: Session = Depends(get_db),
):

    items = get_low_stock_items(db)

    return [
        inventory_to_dict(item)
        for item in items
    ]


# ============================================================
# GET INVENTORY STATISTICS
# ============================================================

@app.get("/api/inventory/stats")
def inventory_stats(
    db: Session = Depends(get_db),
):

    return get_inventory_stats(db)


# ============================================================
# GET SINGLE COMPONENT
# ============================================================

@app.get(
    "/api/inventory/component/{name}"
)
def component(
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


# ============================================================
# FRONTEND COMPATIBILITY API
#
# /api/component?name=ESP32-CAM
# ============================================================

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


# ============================================================
# GET COMPONENTS BY CATEGORY
# ============================================================

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

    matching_items = [

        item

        for item in items

        if item.category

        and item.category.lower()
        == category.strip().lower()
    ]

    return [
        inventory_to_dict(item)
        for item in matching_items
    ]


# ============================================================
# SEARCH INVENTORY
# ============================================================

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


# ============================================================
# UPDATE STOCK
# ============================================================

@app.put(
    "/api/inventory/{item_id}/stock"
)
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

        "message":
            "Stock updated successfully.",

        "item":
            inventory_to_dict(item),
    }


# ============================================================
# CREATE REORDER REQUEST
# ============================================================

@app.post("/api/reorders")
def reorder(
    data: ReorderRequestBody,
    db: Session = Depends(get_db),
):

    try:

        request_record = create_reorder_request(
            db=db,
            item_id=data.item_id,
            quantity=data.quantity,
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    if not request_record:

        raise HTTPException(
            status_code=404,
            detail="Inventory item not found.",
        )

    reorder_data = reorder_to_dict(
        request_record
    )

    return {
        **reorder_data,
        "message":
            "Reorder request created successfully.",
    }


# ============================================================
# GET REORDER HISTORY
# ============================================================

@app.get("/api/reorders")
def reorders(
    db: Session = Depends(get_db),
):

    records = get_reorder_requests(db)

    return [
        reorder_to_dict(record)
        for record in records
    ]


# ============================================================
# CHAT API
# ============================================================

# ============================================================
# CHAT API
# ============================================================

@app.post("/api/chat")
async def chat_api(
    data: ChatRequest,
):
    message = data.message.strip()

    if not message:
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty.",
        )

    try:
        answer = await agent_service.ask_agent(message)

        return {
            "type": "ai",
            "answer": answer,
            "message": answer,
            "data": [],
            "sources": ["langchain_agent"],
            "mode": "agent",
        }

    except Exception as exc:
        print(
            "Chat agent error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=500,
            detail="The AI assistant could not process your request.",
        )



# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health():

    return {

        "status":
            "ok",

        "service":
            "inventory-management-system",
    }
#python -m uvicorn app:app --reload --port 8001