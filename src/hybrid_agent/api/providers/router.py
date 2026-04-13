"""Provider management API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from hybrid_agent.api.auth.dependencies import get_current_token_data
from hybrid_agent.api.auth.permissions import ADMIN_GROUP_ROLES, get_group_ids_with_roles, has_group_role
from hybrid_agent.api.auth.service import TokenData
from hybrid_agent.api.providers.schemas import (
    ProviderCreate,
    ProviderHealthResponse,
    ProviderResponse,
    ProviderUpdate,
)
from hybrid_agent.api.providers.service import (
    create_provider,
    delete_provider,
    get_provider,
    list_providers,
    test_provider_health,
    update_provider,
)


providers_router = APIRouter(prefix="/providers", tags=["providers"])


def _ensure_group_scope(token_data: TokenData, group_id: str | None) -> None:
    if token_data.role.lower() == "admin":
        return
    if not group_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="group_id is required for group_admin",
        )
    if not has_group_role(token_data, str(group_id), *ADMIN_GROUP_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Group access not permitted for this provider",
        )


def _ensure_record_access(token_data: TokenData, provider: ProviderResponse) -> None:
    if token_data.role.lower() == "admin":
        return
    provider_group = provider.group_id
    if not provider_group or not has_group_role(token_data, str(provider_group), *ADMIN_GROUP_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Provider access not permitted",
        )


def _require_provider_manager(
    token_data: TokenData = Depends(get_current_token_data),
) -> TokenData:
    if token_data.role.lower() == "admin":
        return token_data
    if get_group_ids_with_roles(token_data, *ADMIN_GROUP_ROLES):
        return token_data
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient role privileges",
    )


@providers_router.post("", response_model=ProviderResponse)
def create_provider_handler(
    payload: ProviderCreate,
    token_data: TokenData = Depends(_require_provider_manager),
) -> ProviderResponse:
    _ensure_group_scope(token_data, payload.group_id)
    return create_provider(payload)


@providers_router.get("", response_model=list[ProviderResponse])
def list_providers_handler(
    token_data: TokenData = Depends(_require_provider_manager),
) -> list[ProviderResponse]:
    role = token_data.role.lower()
    if role == "admin":
        return list_providers()
    group_ids = get_group_ids_with_roles(token_data, *ADMIN_GROUP_ROLES)
    return list_providers(group_ids=group_ids, include_global=False)


@providers_router.get("/{provider_id}", response_model=ProviderResponse)
def get_provider_handler(
    provider_id: str,
    token_data: TokenData = Depends(_require_provider_manager),
) -> ProviderResponse:
    provider = get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    _ensure_record_access(token_data, provider)
    return provider


@providers_router.patch("/{provider_id}", response_model=ProviderResponse)
def update_provider_handler(
    provider_id: str,
    payload: ProviderUpdate,
    token_data: TokenData = Depends(_require_provider_manager),
) -> ProviderResponse:
    provider = get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    _ensure_record_access(token_data, provider)
    if payload.group_id is not None:
        _ensure_group_scope(token_data, payload.group_id)
    updated = update_provider(provider_id, payload)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return updated


@providers_router.delete("/{provider_id}")
def delete_provider_handler(
    provider_id: str,
    token_data: TokenData = Depends(_require_provider_manager),
) -> dict[str, bool]:
    provider = get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    _ensure_record_access(token_data, provider)
    deleted = delete_provider(provider_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return {"success": True}


@providers_router.post("/{provider_id}/health", response_model=ProviderHealthResponse)
def check_provider_health_handler(
    provider_id: str,
    token_data: TokenData = Depends(_require_provider_manager),
) -> ProviderHealthResponse:
    provider = get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    _ensure_record_access(token_data, provider)
    return test_provider_health(provider_id)
