from fastapi import FastAPI
from fastapi.testclient import TestClient
import logging

from observability import request_observability_middleware


def _client() -> TestClient:
    app = FastAPI()
    app.middleware("http")(request_observability_middleware)

    @app.get("/probe")
    def probe():
        return {"ok": True}

    return TestClient(app)


def test_response_contains_generated_request_id():
    response = _client().get("/probe")

    assert response.status_code == 200
    assert response.headers["x-request-id"]


def test_safe_caller_request_id_is_propagated():
    response = _client().get("/probe", headers={"X-Request-ID": "release-check-123"})

    assert response.headers["x-request-id"] == "release-check-123"


def test_unsafe_caller_request_id_is_replaced():
    response = _client().get("/probe", headers={"X-Request-ID": "bad request id\nforged"})

    assert response.headers["x-request-id"] != "bad request id\nforged"


def test_access_log_does_not_contain_secret_headers(caplog):
    caplog.set_level(logging.INFO, logger="vibe_research.http")
    response = _client().get(
        "/probe",
        headers={"Authorization": "Bearer must-not-be-logged", "Cookie": "session=must-not-be-logged"},
    )

    assert response.status_code == 200
    combined = "\n".join(record.getMessage() for record in caplog.records)
    assert "must-not-be-logged" not in combined
    assert "http_request" in combined
