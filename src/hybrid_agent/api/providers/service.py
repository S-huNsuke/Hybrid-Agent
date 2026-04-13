"""Provider CRUD service backed by the shared database layer."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from collections.abc import Iterable
from datetime import datetime
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status

from hybrid_agent.api.providers.schemas import (
    ProviderCreate,
    ProviderHealthResponse,
    ProviderResponse,
    ProviderUpdate,
)
from hybrid_agent.core.config import settings, get_provider_secret_key
from hybrid_agent.core.database import ProviderModel, db_manager
from hybrid_agent.llm.models import clear_provider_model_cache


def _get_cipher() -> Fernet:
    secret = get_provider_secret_key()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Provider secret key is not configured",
        )

    key_bytes = secret.encode("utf-8")
    if len(key_bytes) != 44:
        key_bytes = base64.urlsafe_b64encode(key_bytes.ljust(32, b"0")[:32])
    return Fernet(key_bytes)


def _mask_api_key(api_key: str | None) -> tuple[str | None, bool]:
    if not api_key:
        return None, False
    last4 = api_key[-4:] if len(api_key) >= 4 else api_key
    hint = f"****{last4}" if last4 else "****"
    return hint, True


def _encrypt_api_key(api_key: str | None) -> tuple[str, str | None]:
    if not api_key:
        return "", None
    hint, _ = _mask_api_key(api_key)
    token = _get_cipher().encrypt(api_key.encode("utf-8")).decode("utf-8")
    return token, hint


def _decrypt_api_key(ciphertext: str | None) -> str | None:
    if not ciphertext:
        return None
    try:
        return _get_cipher().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored provider key cannot be decrypted",
        ) from exc


def _parse_models(raw_models: str | None) -> list[str]:
    if not raw_models:
        return []
    try:
        parsed = json.loads(raw_models)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        pass
    return [item.strip() for item in raw_models.split(",") if item.strip()]


def _serialize_models(models: list[str] | None) -> str:
    return json.dumps(models or [], ensure_ascii=False)


def _to_response(record: ProviderModel) -> ProviderResponse:
    return ProviderResponse(
        id=str(record.id),
        provider_type=str(record.provider_type),
        display_name=str(record.display_name),
        base_url=str(record.base_url) if record.base_url else None,
        models=_parse_models(str(record.models) if record.models else None),
        default_model=str(record.default_model) if record.default_model else None,
        group_id=str(record.group_id) if record.group_id else None,
        is_active=bool(record.is_active),
        api_key_hint=str(record.api_key_hint) if record.api_key_hint else None,
        has_api_key=bool(record.api_key_ciphertext),
        created_at=record.created_at if isinstance(record.created_at, datetime) else None,
        updated_at=record.updated_at if isinstance(record.updated_at, datetime) else None,
    )


def _resolve_probe_base_url(record: ProviderModel) -> str | None:
    if record.base_url:
        return str(record.base_url).rstrip("/")

    provider_type = str(record.provider_type).lower()
    if provider_type == "deepseek":
        return str(settings.deepseek_base_url or "").rstrip("/") or None
    if provider_type == "qwen":
        return str(settings.qwen_base_url or settings.qwen_omni_base_url or "").rstrip("/") or None
    if provider_type in {"openai", "openai_compatible", "custom", "azure_openai"}:
        return "https://api.openai.com/v1"
    return None


def _health_response(
    *,
    provider_id: str,
    ok: bool,
    status: str,
    message: str,
    model: str | None,
    latency_ms: int | None = None,
    http_status: int | None = None,
    error: str | None = None,
) -> ProviderHealthResponse:
    return ProviderHealthResponse(
        provider_id=provider_id,
        ok=ok,
        status=status,
        message=message,
        latency_ms=latency_ms,
        model=model,
        http_status=http_status,
        error=error,
    )


def test_provider_health(provider_id: str) -> ProviderHealthResponse:
    record = db_manager.get_provider(provider_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found",
        )

    model = str(record.default_model).strip() if record.default_model else None
    api_key = _decrypt_api_key(
        str(record.api_key_ciphertext) if record.api_key_ciphertext else None
    )
    if not api_key:
        return _health_response(
            provider_id=provider_id,
            ok=False,
            status="missing_api_key",
            message="Provider API key is missing",
            model=model,
            error="Provider API key is missing",
        )

    probe_base_url = _resolve_probe_base_url(record)
    if not probe_base_url:
        return _health_response(
            provider_id=provider_id,
            ok=False,
            status="missing_base_url",
            message="Provider base URL is not configured",
            model=model,
            error="Provider base URL is not configured",
        )

    request = urllib.request.Request(
        url=f"{probe_base_url}/models",
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Hybrid-Agent/1.0",
        },
        method="GET",
    )
    started_at = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            response.read(1)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return _health_response(
            provider_id=provider_id,
            ok=True,
            status="healthy",
            message="Provider endpoint is reachable",
            latency_ms=latency_ms,
            model=model,
        )
    except urllib.error.HTTPError as exc:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        detail = exc.read(256).decode("utf-8", errors="ignore").strip()
        status_code = "auth_error" if exc.code in {401, 403} else "http_error"
        message = (
            f"Provider authentication failed (HTTP {exc.code})"
            if status_code == "auth_error"
            else f"Provider endpoint returned HTTP {exc.code}"
        )
        return _health_response(
            provider_id=provider_id,
            ok=False,
            status=status_code,
            message=message,
            latency_ms=latency_ms,
            model=model,
            http_status=exc.code,
            error=detail or f"HTTP {exc.code}",
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return _health_response(
            provider_id=provider_id,
            ok=False,
            status="network_error",
            message="Provider endpoint is unreachable",
            latency_ms=latency_ms,
            model=model,
            error=str(exc),
        )


def create_provider(payload: ProviderCreate) -> ProviderResponse:
    ciphertext, hint = _encrypt_api_key(payload.api_key)
    record = ProviderModel(
        id=str(uuid4()),
        provider_type=payload.provider_type,
        display_name=payload.display_name,
        base_url=payload.base_url,
        api_key_ciphertext=ciphertext,
        api_key_hint=hint,
        models=_serialize_models(payload.models),
        default_model=payload.default_model,
        group_id=payload.group_id,
        is_active=payload.is_active,
    )
    created = db_manager.create_provider(record)
    clear_provider_model_cache()
    return _to_response(created)


def get_provider(provider_id: str) -> ProviderResponse | None:
    record = db_manager.get_provider(provider_id)
    return _to_response(record) if record else None


def list_providers(
    *,
    group_ids: Iterable[str] | None = None,
    include_global: bool = True,
) -> list[ProviderResponse]:
    if group_ids is None:
        return [_to_response(record) for record in db_manager.list_providers(include_inactive=True)]

    allowed = {str(group_id) for group_id in group_ids}
    filtered: list[ProviderResponse] = []

    if include_global:
        filtered.extend(
            _to_response(record)
            for record in db_manager.list_providers(group_id=None, include_inactive=True)
        )

    for group_id in allowed:
        filtered.extend(
            _to_response(record)
            for record in db_manager.list_providers(group_id=group_id, include_inactive=True)
        )

    deduped: dict[str, ProviderResponse] = {provider.id: provider for provider in filtered}
    return list(deduped.values())


def update_provider(provider_id: str, payload: ProviderUpdate) -> ProviderResponse | None:
    updates = payload.model_dump(exclude_unset=True)
    api_key_ciphertext = None
    api_key_hint = None
    if "api_key" in updates:
        api_key_ciphertext, api_key_hint = _encrypt_api_key(updates.pop("api_key"))

    updated = db_manager.update_provider(
        provider_id,
        group_id=updates.get("group_id"),
        provider_type=updates.get("provider_type"),
        display_name=updates.get("display_name"),
        base_url=updates.get("base_url"),
        api_key_ciphertext=api_key_ciphertext,
        api_key_hint=api_key_hint,
        models=_serialize_models(updates.get("models")) if "models" in updates else None,
        default_model=updates.get("default_model"),
        is_active=updates.get("is_active"),
    )
    if updated:
        clear_provider_model_cache()
    return _to_response(updated) if updated else None


def delete_provider(provider_id: str) -> bool:
    deleted = db_manager.delete_provider(provider_id)
    if deleted:
        clear_provider_model_cache()
    return deleted
