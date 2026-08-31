import logging
from pathlib import Path
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Request, Depends, HTTPException
# pyrefly: ignore [missing-import]
from fastapi.responses import HTMLResponse, RedirectResponse
# pyrefly: ignore [missing-import]
from fastapi.templating import Jinja2Templates
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from config import TEMPLATES_DIR, DATABASE_PATH
from database.models import get_db, User
from database.mongodb import check_mongo_health
from services.auth_service import get_current_user_optional, hash_password
from services.analytics_service import get_dashboard_analytics, get_inventory_stats

logger = logging.getLogger("routes.dashboard")

router = APIRouter(tags=["Dashboard & Web Pages"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/api/dashboard/analytics")
def dashboard_analytics():
    """Comprehensive MongoDB analytics for the dashboard charts & tables."""
    return get_dashboard_analytics()


@router.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "inventory-management-system",
        "sqlite_db": str(DATABASE_PATH),
        "mongodb": check_mongo_health(),
    }


# ============================================================
# WEB PAGES
# ============================================================

@router.get("/")
def root(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if user:
        return RedirectResponse(url="/chat", status_code=303)
    return RedirectResponse(url="/login", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if user:
        return RedirectResponse(url="/chat", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"request": request},
    )


@router.get("/chat", response_class=HTMLResponse)
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


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    stats = get_inventory_stats()
    mongo_health = check_mongo_health()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "user": user,
            "stats": stats,
            "mongo_health": mongo_health,
        },
    )


@router.get("/inventory", response_class=HTMLResponse)
def inventory_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    stats = get_inventory_stats()
    mongo_health = check_mongo_health()

    return templates.TemplateResponse(
        request=request,
        name="inventory.html",
        context={
            "request": request,
            "user": user,
            "stats": stats,
            "mongo_health": mongo_health,
        },
    )
