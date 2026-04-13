"""RBAC helpers that build on the core auth dependencies."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Callable

from fastapi import Depends, HTTPException, status

from hybrid_agent.api.auth.dependencies import get_current_token_data
from hybrid_agent.api.auth.service import TokenData

ADMIN_GROUP_ROLES = {"admin", "group_admin"}


def _normalize_roles(roles: Iterable[str]) -> set[str]:
    return {role.lower().strip() for role in roles if role}


def get_group_role(token_data: TokenData, group_id: str) -> str | None:
    return token_data.group_roles.get(str(group_id))


def has_group_role(token_data: TokenData, group_id: str, *roles: str) -> bool:
    group_role = get_group_role(token_data, group_id)
    if not group_role:
        return False
    if not roles:
        return True
    return group_role.lower() in _normalize_roles(roles)


def get_group_ids_with_roles(token_data: TokenData, *roles: str) -> list[str]:
    if not roles:
        return [str(group_id) for group_id in token_data.group_roles.keys()]

    allowed = _normalize_roles(roles)
    return [
        str(group_id)
        for group_id, role in token_data.group_roles.items()
        if str(role).lower() in allowed
    ]


def resolve_requested_group_id(
    token_data: TokenData | None,
    requested_group_id: str | None,
    *,
    require_explicit_if_multiple: bool = False,
) -> str | None:
    if requested_group_id:
        if token_data is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        if token_data.role.lower() == "admin" or str(requested_group_id) in token_data.group_roles:
            return str(requested_group_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requested group is not accessible",
        )

    if token_data is None:
        return None

    group_ids = [str(group_id) for group_id in token_data.group_ids if group_id]
    if len(group_ids) == 1:
        return group_ids[0]
    if require_explicit_if_multiple and len(group_ids) > 1 and token_data.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="group_id is required when multiple groups are available",
        )
    return None


def require_role(*roles: str) -> Callable[..., TokenData]:
    """Ensure the authenticated token has one of the requested global roles."""

    if not roles:
        raise ValueError("require_role requires at least one role")
    allowed = _normalize_roles(roles)

    def dependency(token_data: TokenData = Depends(get_current_token_data)) -> TokenData:
        current_role = token_data.role.lower()
        if current_role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role privileges",
            )
        return token_data

    return dependency


def require_group_access(allowed_roles: Iterable[str] | None = None) -> Callable[..., TokenData]:
    """Enforce membership (and optional role) for `group_id` path params."""

    allowed = _normalize_roles(allowed_roles) if allowed_roles else None

    def dependency(
        group_id: str,
        token_data: TokenData = Depends(get_current_token_data),
    ) -> TokenData:
        group_role = token_data.group_roles.get(str(group_id))
        if not group_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not a member of the requested group",
            )
        normalized = group_role.lower()
        if allowed and normalized not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Group membership role not sufficient",
            )
        return token_data

    return dependency
