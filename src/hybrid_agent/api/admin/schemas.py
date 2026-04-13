"""Pydantic schema for admin payloads/responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class UserGroupDetail(BaseModel):
    group_id: str
    group_name: str | None
    role: str


class UserSummary(BaseModel):
    id: str
    username: str
    email: str | None
    role: str
    is_active: bool
    groups: list[UserGroupDetail] = Field(default_factory=list)


class GroupMemberSummary(BaseModel):
    user_id: str
    username: str | None
    role: str


class GroupSummary(BaseModel):
    id: str
    name: str
    description: str | None
    members: list[GroupMemberSummary] = Field(default_factory=list)


class GroupCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None


class GroupMemberRequest(BaseModel):
    user_id: str
    role: str = Field(default="member")


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6)
    email: str | None = None
    role: str = Field(default="member")
    is_active: bool = Field(default=True)
