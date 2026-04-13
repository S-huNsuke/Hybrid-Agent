"""Pydantic schemas for provider management."""

from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class ProviderCreate(BaseModel):
    provider_type: str = Field(..., description="Provider identifier (e.g., openai, deepseek)")
    display_name: str = Field(..., description="Human-friendly provider name")
    base_url: str | None = Field(None, description="Optional custom base URL")
    api_key: str | None = Field(None, description="Provider API key (stored securely, not returned)")
    models: List[str] = Field(default_factory=list, description="Allowed model IDs")
    default_model: str | None = Field(None, description="Default model ID")
    group_id: str | None = Field(None, description="Tenant group id (required for group_admin)")
    is_active: bool = Field(True, description="Whether provider is active")


class ProviderUpdate(BaseModel):
    display_name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    models: List[str] | None = None
    default_model: str | None = None
    group_id: str | None = None
    is_active: bool | None = None


class ProviderResponse(BaseModel):
    id: str
    provider_type: str
    display_name: str
    base_url: str | None = None
    models: List[str] = Field(default_factory=list)
    default_model: str | None = None
    group_id: str | None = None
    is_active: bool = True
    api_key_hint: str | None = None
    has_api_key: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProviderHealthResponse(BaseModel):
    provider_id: str
    ok: bool
    status: str = Field(..., description="Machine-readable health status")
    message: str = Field(..., description="User-facing health summary")
    latency_ms: int | None = None
    model: str | None = None
    http_status: int | None = None
    error: str | None = None


__all__ = [
    "ProviderCreate",
    "ProviderUpdate",
    "ProviderResponse",
    "ProviderHealthResponse",
]
