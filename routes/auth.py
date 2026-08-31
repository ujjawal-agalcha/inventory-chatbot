import logging
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Request, Response, Depends, HTTPException, status
# pyrefly: ignore [missing-import]
from fastapi.responses import RedirectResponse
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from database.models import get_db, User
from schemas.auth import UserRegisterRequest, UserLoginRequest, UserResponse, AuthTokenResponse
from services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_current_user_optional,
)

logger = logging.getLogger("routes.auth")

router = APIRouter(tags=["Authentication"])


@router.post("/api/auth/register", response_model=AuthTokenResponse)
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


@router.post("/api/auth/login", response_model=AuthTokenResponse)
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


@router.get("/api/auth/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "email": user.email,
    }


@router.get("/logout")
def logout(response: Response, request: Request):
    request.session.clear()
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie("access_token")
    resp.delete_cookie("inventory_session")
    return resp
