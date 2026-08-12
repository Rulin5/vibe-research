from uuid import uuid4

from fastapi.testclient import TestClient

import app as app_module
from db import get_session
from models import User, UserAiCredential


ORIGIN = "http://127.0.0.1:5900"


def _client() -> tuple[TestClient, str]:
    username = f"ai_{uuid4().hex[:16]}"
    client = TestClient(app_module.app)
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "CorrectHorseBatteryStaple!9", "phone": "19198273569"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 201
    return client, username


def _headers(client: TestClient) -> dict[str, str]:
    return {"Origin": ORIGIN, "X-CSRF-Token": client.cookies.get("vr_csrf", "")}


def _delete_user(username: str) -> None:
    session = next(get_session())
    try:
        user = session.query(User).filter(User.username == username).one_or_none()
        if user is not None:
            session.delete(user)
            session.commit()
    finally:
        session.close()


def test_ai_credential_is_encrypted_and_never_returned_to_browser():
    client, username = _client()
    secret = "stepfun-test-secret-that-must-not-be-returned"
    try:
        assert client.put("/api/ai/credential", json={"api_key": secret, "base_url": "https://api.stepfun.com/step_plan/v1", "model": "step-3.7-flash"}, headers=_headers(client)).status_code == 200
        status = client.get("/api/ai/credential")
        assert status.status_code == 200
        assert status.json()["data"] == {"configured": True, "active_source": "user", "provider": "stepfun", "base_url": "https://api.stepfun.com/step_plan/v1", "model": "step-3.7-flash", "key_suffix": secret[-4:]}
        assert secret not in status.text
        session = next(get_session())
        try:
            row = session.query(UserAiCredential).filter(UserAiCredential.user_id == client.get("/api/auth/me").json()["data"]["id"]).one()
            assert row.encrypted_secret != secret
        finally:
            session.close()
        assert client.delete("/api/ai/credential", headers=_headers(client)).status_code == 204
        assert client.get("/api/ai/credential").json()["data"]["configured"] is False
    finally:
        _delete_user(username)


def test_ai_stream_requires_authenticated_server_credential(monkeypatch):
    client, username = _client()
    monkeypatch.delenv("VR_AI_STEPFUN_API_KEY", raising=False)
    try:
        assert client.post("/api/chat", json={"messages": [{"role": "user", "content": "x"}]}, headers=_headers(client)).status_code == 422
        assert client.put("/api/ai/credential", json={"api_key": "stepfun-test-secret-that-must-not-be-returned", "base_url": "https://api.stepfun.com/step_plan/v1", "model": "step-3.7-flash"}, headers=_headers(client)).status_code == 200
        captured = {}
        def fake_stream(config, messages, context):
            captured.update(config)
            yield {"type": "done", "trace": [], "rounds": 1}
        monkeypatch.setattr(app_module.chat_layer, "run_chat_stream", fake_stream)
        response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "x"}]}, headers=_headers(client))
        assert response.status_code == 200
        assert captured["baseURL"] == "https://api.stepfun.com/step_plan/v1"
        assert captured["model"] == "step-3.7-flash"
    finally:
        _delete_user(username)


def test_ai_stream_falls_back_to_system_key_until_user_saves_a_personal_key(monkeypatch):
    client, username = _client()
    monkeypatch.setenv("VR_AI_STEPFUN_API_KEY", "system-test-key-that-is-not-a-user-key")
    captured = {}
    def fake_stream(config, messages, context):
        captured.update(config)
        yield {"type": "done", "trace": [], "rounds": 1}
    monkeypatch.setattr(app_module.chat_layer, "run_chat_stream", fake_stream)
    try:
        response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "x"}]}, headers=_headers(client))
        assert response.status_code == 200
        assert captured["apiKey"] == "system-test-key-that-is-not-a-user-key"
    finally:
        _delete_user(username)


def test_user_ai_configuration_overrides_system_endpoint_and_model(monkeypatch):
    client, username = _client()
    payload = {"api_key": "user-custom-key-that-must-not-be-returned", "base_url": "https://example.com/v1", "model": "user-model"}
    captured = {}
    def fake_stream(config, messages, context):
        captured.update(config)
        yield {"type": "done", "trace": [], "rounds": 1}
    monkeypatch.setattr(app_module.chat_layer, "run_chat_stream", fake_stream)
    try:
        assert client.put("/api/ai/credential", json=payload, headers=_headers(client)).status_code == 200
        assert client.post("/api/chat", json={"messages": [{"role": "user", "content": "x"}]}, headers=_headers(client)).status_code == 200
        assert captured["baseURL"] == payload["base_url"]
        assert captured["model"] == payload["model"]
        assert captured["apiKey"] == payload["api_key"]
    finally:
        _delete_user(username)
