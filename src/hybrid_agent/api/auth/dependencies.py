"""Dependencies for auth-protected endpoints."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from hybrid_agent.api.auth.service import TokenData, auth_service
from hybrid_agent.core.database import UserModel


__all__ = ["get_current_token_data", "get_current_user"]


_bearer_scheme = HTTPBearer(auto_error=False)


def _require_bearer_token(credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme)) -> str:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or malformed",
        )
    return credentials.credentials


def get_current_token_data(token: str = Depends(_require_bearer_token)) -> TokenData:
    return auth_service.decode_access_token(token)


def get_current_user(token_data: TokenData = Depends(get_current_token_data)) -> UserModel:
    user = auth_service.get_user_by_id(token_data.user_id)
    if not user or not bool(getattr(user, "is_active", True)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive"
        )
    return user
