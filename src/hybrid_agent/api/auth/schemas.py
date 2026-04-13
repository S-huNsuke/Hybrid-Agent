"""Pydantic schemas for auth endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., description="系统用户名")
    password: str = Field(..., description="用户密码")


class RegisterRequest(BaseModel):
    username: str = Field(..., description="系统用户名")
    password: str = Field(..., min_length=6, description="用户密码")
    email: str | None = Field(None, description="可选邮箱")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = Field("bearer", description="Token 类型")
    expires_at: int = Field(..., description="Unix 时间戳（秒）")


class UserInfo(BaseModel):
    id: str
    username: str
    email: str | None = None
    created_at: datetime | None = None
    group_ids: List[str] = Field(default_factory=list)
    group_roles: dict[str, str] = Field(default_factory=dict)
    role: str = "member"
