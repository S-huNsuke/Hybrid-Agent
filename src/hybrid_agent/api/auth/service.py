"""Authentication helpers for JWT and user verification."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from hybrid_agent.core.database import UserGroupModel, UserModel, db_manager


@dataclass(frozen=True)
class TokenData:
    user_id: str
    group_ids: list[str]
    group_roles: dict[str, str]
    role: str
    exp: int


class AuthService:
    def __init__(self) -> None:
        self._pwd_context = CryptContext(
            schemes=["pbkdf2_sha256", "bcrypt"],
            deprecated="auto",
        )

    def _get_jwt_config(self) -> tuple[str, str, int]:
        secret_key = os.getenv("JWT_SECRET_KEY")
        if not secret_key or secret_key.strip() == "change-me":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="JWT secret key is not configured",
            )
        algorithm = os.getenv("JWT_ALGORITHM") or "HS256"
        access_token_minutes = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
        return secret_key, algorithm, access_token_minutes

    def _open_session(self) -> Any:
        if not db_manager or not db_manager.SessionLocal:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database unavailable"
            )
        return db_manager.SessionLocal()

    def _get_group_ids(self, user_id: str) -> list[str]:
        session = self._open_session()
        try:
            rows = (
                session.query(UserGroupModel.group_id)
                .filter(UserGroupModel.user_id == user_id)
                .all()
            )
            return [str(row[0]) for row in rows if row and row[0]]
        finally:
            session.close()

    def get_user_group_ids(self, user_id: str) -> list[str]:
        return self._get_group_ids(user_id)

    def _get_group_roles(self, user_id: str) -> dict[str, str]:
        session = self._open_session()
        try:
            rows = (
                session.query(UserGroupModel.group_id, UserGroupModel.role)
                .filter(UserGroupModel.user_id == user_id)
                .all()
            )
            result: dict[str, str] = {}
            for group_id, role in rows:
                if not group_id:
                    continue
                result[str(group_id)] = role or "member"
            return result
        finally:
            session.close()

    def _resolve_role(self, user: UserModel, group_roles: dict[str, str]) -> str:
        if hasattr(user, "role") and getattr(user, "role"):
            return str(getattr(user, "role"))
        lower_roles = {r.lower() for r in group_roles.values()}
        if "admin" in lower_roles:
            return "admin"
        if "group_admin" in lower_roles:
            return "group_admin"
        return "member"

    def create_access_token(
        self, user: UserModel, expires_delta: timedelta | None = None
    ) -> tuple[str, int]:
        secret_key, algorithm, access_token_minutes = self._get_jwt_config()
        user_id = str(user.id)
        group_roles = self._get_group_roles(user_id)
        group_ids = list(group_roles.keys())
        now = datetime.now(UTC)
        expire = now + (expires_delta or timedelta(minutes=access_token_minutes))
        expires_at = int(expire.timestamp())
        payload = {
            "sub": user_id,
            "group_ids": group_ids,
            "group_roles": group_roles,
            "role": self._resolve_role(user, group_roles),
            "exp": expires_at,
        }
        token = jwt.encode(payload, secret_key, algorithm=algorithm)
        return token, expires_at

    def _fetch_user_by_username(self, username: str) -> UserModel | None:
        session = self._open_session()
        try:
            return (
                session.query(UserModel)
                .filter(UserModel.username == username)
                .first()
            )
        finally:
            session.close()

    def get_user_by_id(self, user_id: str) -> UserModel | None:
        session = self._open_session()
        try:
            return session.query(UserModel).filter(UserModel.id == user_id).first()
        finally:
            session.close()

    def verify_password(self, plain_password: str, hashed_password: str | None) -> bool:
        if not hashed_password:
            return False
        return self._pwd_context.verify(plain_password, hashed_password)

    def authenticate(self, username: str, password: str) -> UserModel:
        user = self._fetch_user_by_username(username)
        hashed_password = str(user.hashed_password) if user and user.hashed_password else None
        if not user or not self.verify_password(password, hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )
        if not bool(getattr(user, "is_active", True)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled"
            )
        return user

    def register(
        self,
        username: str,
        password: str,
        email: str | None = None,
    ) -> UserModel:
        session = self._open_session()
        try:
            existing = session.query(UserModel).filter(UserModel.username == username).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already exists",
                )

            user_count = session.query(UserModel).count()
            role = "admin" if user_count == 0 else "member"
            user = UserModel(
                id=str(os.urandom(16).hex()),
                username=username,
                email=email,
                hashed_password=self._pwd_context.hash(password),
                role=role,
                is_active=True,
            )
            session.add(user)
            session.flush()
            session.commit()
            session.refresh(user)
            return user
        finally:
            session.close()

    def decode_access_token(self, token: str) -> TokenData:
        secret_key, algorithm, _ = self._get_jwt_config()
        try:
            payload = jwt.decode(token, secret_key, algorithms=[algorithm])
            user_id = payload.get("sub")
            exp = payload.get("exp")
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )
        if not user_id or not exp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token"
            )
        user = self.get_user_by_id(str(user_id))
        if not user or not bool(getattr(user, "is_active", True)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive"
            )
        normalized_roles = self._get_group_roles(str(user_id))
        group_ids = list(normalized_roles.keys())
        return TokenData(
            user_id=str(user_id),
            group_ids=group_ids,
            group_roles=normalized_roles,
            role=self._resolve_role(user, normalized_roles),
            exp=int(exp),
        )

    def refresh_access_token(self, token: str) -> tuple[str, int]:
        data = self.decode_access_token(token)
        user = self.get_user_by_id(data.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
            )
        return self.create_access_token(user)


auth_service = AuthService()
