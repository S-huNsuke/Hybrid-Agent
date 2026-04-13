from __future__ import annotations

import importlib
from types import SimpleNamespace

from fastapi.testclient import TestClient
from jose import jwt

from hybrid_agent.api.main import app
from hybrid_agent.api.auth.service import TokenData, auth_service
from hybrid_agent.core import database as database_module
from hybrid_agent.api.providers import service as provider_service
from hybrid_agent.llm import models as llm_models


client = TestClient(app)
chat_routes = importlib.import_module("hybrid_agent.api.routes.chat")
document_routes = importlib.import_module("hybrid_agent.api.routes.documents")


def test_v1_documents_routes_require_authentication() -> None:
    response = client.get("/api/v1/documents")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}

    task_response = client.get("/api/v1/documents/tasks/task-1")
    assert task_response.status_code == 401
    assert task_response.json() == {"detail": "Not authenticated"}


def test_legacy_documents_route_requires_api_key_or_token() -> None:
    response = client.get("/api/documents")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_decode_access_token_uses_live_user_role_state(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret")
    token = jwt.encode(
        {
            "sub": "user-1",
            "role": "admin",
            "group_ids": ["group-1"],
            "group_roles": {"group-1": "group_admin"},
            "exp": 2_000_000_000,
        },
        "test-jwt-secret",
        algorithm="HS256",
    )
    monkeypatch.setattr(
        auth_service,
        "get_user_by_id",
        lambda user_id: SimpleNamespace(id=user_id, role="member", is_active=True),
    )
    monkeypatch.setattr(
        auth_service,
        "_get_group_roles",
        lambda _user_id: {"group-2": "member"},
    )

    token_data = auth_service.decode_access_token(token)

    assert token_data.user_id == "user-1"
    assert token_data.role == "member"
    assert token_data.group_ids == ["group-2"]
    assert token_data.group_roles == {"group-2": "member"}


def test_decode_access_token_rejects_inactive_user(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret")
    token = jwt.encode(
        {"sub": "user-2", "exp": 2_000_000_000},
        "test-jwt-secret",
        algorithm="HS256",
    )
    monkeypatch.setattr(
        auth_service,
        "get_user_by_id",
        lambda user_id: SimpleNamespace(id=user_id, role="member", is_active=False),
    )

    try:
        auth_service.decode_access_token(token)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 401
        assert getattr(exc, "detail", None) == "User not found or inactive"
    else:
        raise AssertionError("decode_access_token should reject inactive users")


def test_authenticate_rejects_inactive_user(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_service,
        "_fetch_user_by_username",
        lambda _username: SimpleNamespace(
            id="user-3",
            hashed_password="hashed",
            is_active=False,
        ),
    )
    monkeypatch.setattr(auth_service, "verify_password", lambda *_args: True)

    try:
        auth_service.authenticate("disabled", "password")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
        assert getattr(exc, "detail", None) == "User account is disabled"
    else:
        raise AssertionError("authenticate should reject inactive users")


def test_provider_crypto_roundtrip_uses_shared_secret(monkeypatch) -> None:
    monkeypatch.delenv("PROVIDER_SECRET_KEY", raising=False)
    monkeypatch.setenv("JWT_SECRET_KEY", "shared-provider-secret")

    ciphertext, _hint = provider_service._encrypt_api_key("sk-provider")

    assert llm_models._decrypt_provider_api_key(ciphertext) == "sk-provider"


def test_provider_cache_is_cleared_on_mutation(monkeypatch) -> None:
    llm_models._provider_model_cache[("base", "group-1", "")] = object()

    record = SimpleNamespace(
        id="provider-1",
        provider_type="openai",
        display_name="Provider 1",
        base_url="https://api.example.test/v1",
        models='["gpt-4.1-mini"]',
        default_model="gpt-4.1-mini",
        group_id="group-1",
        is_active=True,
        api_key_hint="****1234",
        api_key_ciphertext="cipher",
        created_at=None,
        updated_at=None,
    )
    monkeypatch.setattr(provider_service.db_manager, "update_provider", lambda *_args, **_kwargs: record)

    updated = provider_service.update_provider(
        "provider-1",
        provider_service.ProviderUpdate(display_name="Updated"),
    )

    assert updated is not None
    assert llm_models._provider_model_cache == {}


def test_multi_group_chat_requires_explicit_group_selection() -> None:
    app.dependency_overrides[chat_routes._get_optional_token_data] = lambda: TokenData(
        user_id="user-4",
        group_ids=["group-1", "group-2"],
        group_roles={"group-1": "member", "group-2": "member"},
        role="member",
        exp=2_000_000_000,
    )
    try:
        response = client.post(
            "/api/v1/chat",
            json={"message": "hello", "stream": False},
        )
    finally:
        app.dependency_overrides.pop(chat_routes._get_optional_token_data, None)

    assert response.status_code == 400
    assert response.json() == {"detail": "group_id is required when multiple groups are available"}


def test_chat_sessions_list_is_not_forced_to_first_group(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_list_chat_sessions(*, user_id, group_id=None, limit=None, offset=None):
        captured["user_id"] = user_id
        captured["group_id"] = group_id
        return []

    monkeypatch.setattr(database_module.db_manager, "list_chat_sessions", _fake_list_chat_sessions)
    app.dependency_overrides[chat_routes._require_token_data] = lambda: TokenData(
        user_id="user-5",
        group_ids=["group-1", "group-2"],
        group_roles={"group-1": "member", "group-2": "member"},
        role="member",
        exp=2_000_000_000,
    )
    try:
        response = client.get("/api/v1/chat/sessions")
    finally:
        app.dependency_overrides.pop(chat_routes._require_token_data, None)

    assert response.status_code == 200
    assert captured == {"user_id": "user-5", "group_id": None}


def test_documents_list_aggregates_accessible_groups_instead_of_first_group(monkeypatch) -> None:
    class _Doc:
        def __init__(self, doc_id: str, filename: str, group_id: str | None) -> None:
            self.id = doc_id
            self.filename = filename
            self.group_id = group_id
            self.file_size = 1
            self.status = "ready"
            self.created_at = None

    monkeypatch.setattr(database_module.db_manager, "list_documents_without_group", lambda: [_Doc("global-1", "global.txt", None)])
    monkeypatch.setattr(
        database_module.db_manager,
        "list_documents_by_group_ids",
        lambda group_ids: [_Doc("group-2-doc", "group2.txt", "group-2")] if list(group_ids) == ["group-1", "group-2"] else [],
    )
    app.dependency_overrides[document_routes._require_token_data] = lambda: TokenData(
        user_id="user-6",
        group_ids=["group-1", "group-2"],
        group_roles={"group-1": "member", "group-2": "member"},
        role="member",
        exp=2_000_000_000,
    )
    try:
        response = client.get("/api/v1/documents")
    finally:
        app.dependency_overrides.pop(document_routes._require_token_data, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert {item["id"] for item in payload["documents"]} == {"global-1", "group-2-doc"}
