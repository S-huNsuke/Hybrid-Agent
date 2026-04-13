import importlib

from fastapi.testclient import TestClient

from hybrid_agent.api.main import app
from hybrid_agent.api.schemas import ChatResponse


client = TestClient(app)
chat_routes = importlib.import_module("hybrid_agent.api.routes.chat")


def test_chat_sessions_route_is_mounted() -> None:
    response = client.get("/api/v1/chat/sessions")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_chat_route_uses_router_implementation(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_chat(request, group_id=None, token_data=None):
        captured["message"] = request.message
        captured["group_id"] = group_id
        captured["token_data"] = token_data
        return ChatResponse(
            success=True,
            message="stubbed",
            session_id=request.session_id,
            model_used="stub-model",
            sources=[],
        )

    monkeypatch.setattr(chat_routes, "chat", fake_chat)

    response = client.post(
        "/api/v1/chat",
        json={"message": "hello", "stream": False, "session_id": "session-1"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "stubbed"
    assert captured == {
        "message": "hello",
        "group_id": None,
        "token_data": None,
    }


def test_models_route_is_mounted_and_returns_list() -> None:
    response = client.get("/api/v1/models")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload
    for item in payload:
        assert isinstance(item.get("id"), str)
        assert isinstance(item.get("name"), str)
        assert isinstance(item.get("description"), str)


def test_legacy_models_route_bridges_to_v1() -> None:
    v1_response = client.get("/api/v1/models")
    legacy_response = client.get("/api/models")

    assert v1_response.status_code == 200
    assert legacy_response.status_code == 200
    assert legacy_response.json() == v1_response.json()
