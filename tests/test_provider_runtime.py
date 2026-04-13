import importlib
from typing import Any
from fastapi.testclient import TestClient

from hybrid_agent.api.main import app


client = TestClient(app)
chat_routes = importlib.import_module("hybrid_agent.api.routes.chat")
provider_service = importlib.import_module("hybrid_agent.api.providers.service")
providers_router = importlib.import_module("hybrid_agent.api.providers.router")
provider_schemas = importlib.import_module("hybrid_agent.api.providers.schemas")
auth_dependencies = importlib.import_module("hybrid_agent.api.auth.dependencies")
auth_service = importlib.import_module("hybrid_agent.api.auth.service")


class _FakeRAGSystem:
    def __init__(self, result: dict[str, Any]) -> None:
        self._result = result

    def query(self, **_: Any) -> dict[str, Any]:
        return self._result


def test_chat_model_used_passthrough_from_rag_result(monkeypatch) -> None:
    monkeypatch.setattr(
        chat_routes,
        "get_rag_system",
        lambda: _FakeRAGSystem(
            {
                "success": True,
                "answer": "ok",
                "model_used": "provider/openai:gpt-4.1-mini",
                "sources": [],
            }
        ),
    )
    monkeypatch.setattr(chat_routes, "_touch_chat_session", lambda **_: None)

    response = client.post(
        "/api/v1/chat",
        json={
            "message": "hello",
            "stream": False,
            "use_rag": True,
            "model": "qwen3-omni",
            "session_id": "session-provider-runtime",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["model_used"] == "provider/openai:gpt-4.1-mini"


def test_chat_model_used_fallback_is_non_empty_string(monkeypatch) -> None:
    monkeypatch.setattr(
        chat_routes,
        "get_rag_system",
        lambda: _FakeRAGSystem({"success": True, "answer": "ok", "sources": []}),
    )
    monkeypatch.setattr(chat_routes, "_touch_chat_session", lambda **_: None)

    response = client.post(
        "/api/v1/chat",
        json={
            "message": "hello",
            "stream": False,
            "use_rag": True,
            "model": "qwen3-omni",
            "session_id": "session-provider-fallback",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload.get("model_used"), str)
    assert payload["model_used"]


def test_models_contract_minimum_shape() -> None:
    response = client.get("/api/v1/models")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload

    for item in payload:
        assert isinstance(item.get("id"), str)
        assert isinstance(item.get("name"), str)
        assert isinstance(item.get("description"), str)
        if "is_available" in item:
            assert isinstance(item["is_available"], bool)
        if "provider_type" in item:
            assert isinstance(item["provider_type"], str)


def test_provider_health_service_returns_probe_status(monkeypatch) -> None:
    class ProviderRecord:
        id = "provider-1"
        provider_type = "openai"
        display_name = "OpenAI"
        base_url = "https://api.example.test/v1"
        api_key_ciphertext = "cipher"
        default_model = "gpt-4.1-mini"
        group_id = None
        is_active = True

    provider = ProviderRecord()
    monkeypatch.setattr(provider_service.db_manager, "get_provider", lambda provider_id: provider)
    monkeypatch.setattr(provider_service, "_decrypt_api_key", lambda *_args, **_kwargs: "sk-test")

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _count: int = -1) -> bytes:
            return b"{}"

    monkeypatch.setattr(
        provider_service.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _Response(),
    )

    result = provider_service.test_provider_health("provider-1")

    assert result.provider_id == "provider-1"
    assert result.ok is True
    assert result.status == "healthy"
    assert result.message == "Provider endpoint is reachable"
    assert result.model == "gpt-4.1-mini"


def test_provider_health_service_reports_missing_key_status(monkeypatch) -> None:
    class ProviderRecord:
        id = "provider-2"
        provider_type = "openai"
        display_name = "OpenAI no key"
        base_url = "https://api.example.test/v1"
        api_key_ciphertext = ""
        default_model = "gpt-4.1-mini"
        group_id = None
        is_active = True

    provider = ProviderRecord()
    monkeypatch.setattr(provider_service.db_manager, "get_provider", lambda provider_id: provider)

    result = provider_service.test_provider_health("provider-2")

    assert result.provider_id == "provider-2"
    assert result.ok is False
    assert result.status == "missing_api_key"
    assert result.message == "Provider API key is missing"
    assert result.error == "Provider API key is missing"


def test_providers_endpoint_rejects_readonly_role() -> None:
    app.dependency_overrides[auth_dependencies.get_current_token_data] = lambda: auth_service.TokenData(
        user_id="user-readonly",
        group_ids=["group-1"],
        group_roles={"group-1": "member"},
        role="member",
        exp=2_000_000_000,
    )
    try:
        response = client.get("/api/v1/providers")
    finally:
        app.dependency_overrides.pop(auth_dependencies.get_current_token_data, None)

    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient role privileges"}


def test_providers_endpoint_allows_group_manager_role(monkeypatch) -> None:
    provider = provider_schemas.ProviderResponse(
        id="provider-3",
        provider_type="openai",
        display_name="Group provider",
        base_url="https://api.example.test/v1",
        models=["gpt-4.1-mini"],
        default_model="gpt-4.1-mini",
        group_id="group-1",
        is_active=True,
        has_api_key=True,
    )
    monkeypatch.setattr(
        providers_router,
        "list_providers",
        lambda **_kwargs: [provider],
    )
    app.dependency_overrides[auth_dependencies.get_current_token_data] = lambda: auth_service.TokenData(
        user_id="user-manager",
        group_ids=["group-1"],
        group_roles={"group-1": "group_admin"},
        role="group_admin",
        exp=2_000_000_000,
    )
    try:
        response = client.get("/api/v1/providers")
    finally:
        app.dependency_overrides.pop(auth_dependencies.get_current_token_data, None)

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload
    assert payload[0]["id"] == "provider-3"
    assert payload[0]["group_id"] == "group-1"


def test_providers_endpoint_allows_group_admin_membership_even_if_global_role_is_member(monkeypatch) -> None:
    provider = provider_schemas.ProviderResponse(
        id="provider-4",
        provider_type="openai",
        display_name="Group provider",
        base_url="https://api.example.test/v1",
        models=["gpt-4.1-mini"],
        default_model="gpt-4.1-mini",
        group_id="group-2",
        is_active=True,
        has_api_key=True,
    )
    monkeypatch.setattr(providers_router, "list_providers", lambda **_kwargs: [provider])
    app.dependency_overrides[auth_dependencies.get_current_token_data] = lambda: auth_service.TokenData(
        user_id="user-manager",
        group_ids=["group-1", "group-2"],
        group_roles={"group-1": "member", "group-2": "group_admin"},
        role="member",
        exp=2_000_000_000,
    )
    try:
        response = client.get("/api/v1/providers")
    finally:
        app.dependency_overrides.pop(auth_dependencies.get_current_token_data, None)

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload] == ["provider-4"]


def test_provider_create_requires_admin_role_for_target_group(monkeypatch) -> None:
    called = {"count": 0}

    def _unexpected_create(_payload):
        called["count"] += 1
        raise AssertionError("create_provider should not be called")

    monkeypatch.setattr(providers_router, "create_provider", _unexpected_create)
    app.dependency_overrides[auth_dependencies.get_current_token_data] = lambda: auth_service.TokenData(
        user_id="user-manager",
        group_ids=["group-admin", "group-member"],
        group_roles={"group-admin": "group_admin", "group-member": "member"},
        role="member",
        exp=2_000_000_000,
    )
    try:
        response = client.post(
            "/api/v1/providers",
            json={
                "provider_type": "openai",
                "display_name": "Forbidden provider",
                "group_id": "group-member",
                "models": ["gpt-4.1-mini"],
                "is_active": True,
            },
        )
    finally:
        app.dependency_overrides.pop(auth_dependencies.get_current_token_data, None)

    assert response.status_code == 403
    assert response.json() == {"detail": "Group access not permitted for this provider"}
    assert called["count"] == 0
