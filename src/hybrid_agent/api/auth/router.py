"""FastAPI router for auth endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, status

from hybrid_agent.api.auth.dependencies import get_current_user
from hybrid_agent.api.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserInfo
from hybrid_agent.api.auth.service import auth_service
from hybrid_agent.core.database import UserModel


auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest) -> TokenResponse:
    user = auth_service.authenticate(request.username, request.password)
    token, expires_at = auth_service.create_access_token(user)
    return TokenResponse(access_token=token, token_type="bearer", expires_at=expires_at)


@auth_router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest) -> TokenResponse:
    user = auth_service.register(request.username, request.password, request.email)
    token, expires_at = auth_service.create_access_token(user)
    return TokenResponse(access_token=token, token_type="bearer", expires_at=expires_at)


@auth_router.post("/refresh", response_model=TokenResponse)
def refresh(current_user: UserModel = Depends(get_current_user)) -> TokenResponse:
    token, expires_at = auth_service.create_access_token(current_user)
    return TokenResponse(access_token=token, token_type="bearer", expires_at=expires_at)


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(current_user: UserModel = Depends(get_current_user)) -> None:
    return None


@auth_router.get("/me", response_model=UserInfo)
def me(current_user: UserModel = Depends(get_current_user)) -> UserInfo:
    group_ids = auth_service.get_user_group_ids(str(current_user.id))
    group_roles = auth_service._get_group_roles(str(current_user.id))
    created_at = current_user.created_at
    return UserInfo(
        id=str(current_user.id),
        username=str(current_user.username),
        email=str(current_user.email) if current_user.email else None,
        created_at=created_at if isinstance(created_at, datetime) else None,
        group_ids=group_ids,
        group_roles=group_roles,
        role=auth_service._resolve_role(current_user, group_roles),
    )
