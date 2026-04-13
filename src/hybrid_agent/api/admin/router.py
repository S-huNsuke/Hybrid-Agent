"""Admin 管理接口，暴露基础用户/组管理能力。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from hybrid_agent.api.admin.schemas import (
    GroupCreateRequest,
    GroupMemberRequest,
    GroupSummary,
    UserCreateRequest,
    UserSummary,
)
from hybrid_agent.api.admin.service import admin_service
from hybrid_agent.api.auth.dependencies import get_current_token_data
from hybrid_agent.api.auth.service import TokenData

admin_router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(token_data: TokenData = Depends(get_current_token_data)) -> TokenData:
    if token_data.role != "admin":
        raise admin_service.permission_denied("Admin role required")
    return token_data


def _require_group_admin_or_admin(
    group_id: str,
    token_data: TokenData = Depends(get_current_token_data),
) -> TokenData:
    if token_data.role == "admin":
        return token_data

    group_role = token_data.group_roles.get(group_id, "").lower()
    if group_role not in {"admin", "group_admin"}:
        raise admin_service.permission_denied("Group admin role required")
    return token_data


@admin_router.get("/users", response_model=list[UserSummary])
def list_users(token_data: TokenData = Depends(_require_admin)) -> list[UserSummary]:
    return [UserSummary.model_validate(item) for item in admin_service.list_users()]


@admin_router.post("/users", response_model=UserSummary, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    token_data: TokenData = Depends(_require_admin),
) -> UserSummary:
    return UserSummary.model_validate(
        admin_service.create_user(
            username=payload.username,
            password=payload.password,
            email=payload.email,
            role=payload.role,
            is_active=payload.is_active,
        )
    )


@admin_router.get("/groups", response_model=list[GroupSummary])
def list_groups(token_data: TokenData = Depends(_require_admin)) -> list[GroupSummary]:
    return [GroupSummary.model_validate(item) for item in admin_service.list_groups()]


@admin_router.post("/groups", response_model=GroupSummary, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: GroupCreateRequest,
    token_data: TokenData = Depends(_require_admin),
) -> GroupSummary:
    return GroupSummary.model_validate(
        admin_service.create_group(payload.name, payload.description)
    )


@admin_router.post("/groups/{group_id}/members", status_code=status.HTTP_204_NO_CONTENT)
def add_member(
    group_id: str,
    payload: GroupMemberRequest,
    token_data: TokenData = Depends(_require_group_admin_or_admin),
) -> None:
    admin_service.add_member(group_id, payload.user_id, payload.role)


@admin_router.delete("/groups/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    group_id: str,
    user_id: str,
    token_data: TokenData = Depends(_require_group_admin_or_admin),
) -> None:
    admin_service.remove_member(group_id, user_id)
