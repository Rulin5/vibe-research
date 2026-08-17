import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

import app as app_module
from db import get_session


class BrokenDatabase:
    def execute(self, _statement):
        raise SQLAlchemyError("database unavailable")


class HealthyDatabase:
    class Result:
        @staticmethod
        def scalar_one():
            return 1

    def execute(self, _statement):
        return self.Result()


def test_readiness_returns_503_when_database_is_unavailable():
    with pytest.raises(HTTPException) as exc_info:
        app_module.ready(BrokenDatabase())

    assert exc_info.value.status_code == 503


def test_readiness_returns_503_when_public_redis_is_unavailable(monkeypatch):
    monkeypatch.setattr(app_module, "redis_ready", lambda: False)

    with pytest.raises(HTTPException) as exc_info:
        app_module.ready(HealthyDatabase())

    assert exc_info.value.status_code == 503


def test_database_dependency_failure_returns_503_with_request_id(monkeypatch):
    """A transient database outage must not become an opaque HTTP 500."""
    def unavailable_session():
        raise SQLAlchemyError("database unavailable")
        yield  # pragma: no cover - keeps this function a generator dependency

    app_module.app.dependency_overrides[get_session] = unavailable_session
    try:
        response = TestClient(app_module.app, raise_server_exceptions=False).post(
            "/api/auth/register",
            json={"username": "outage_user", "password": "CorrectHorseBatteryStaple!9", "phone": "19198273569"},
            headers={"Origin": "http://127.0.0.1:5900"},
        )
    finally:
        app_module.app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "数据库服务暂不可用"
    assert response.headers["x-request-id"]


def test_readiness_returns_503_when_sector_snapshot_is_missing(monkeypatch):
    monkeypatch.setattr(app_module._SECTOR_REFRESH, "readiness", lambda: {"ok": False, "reason": "snapshot_missing"})

    with pytest.raises(HTTPException) as exc_info:
        app_module.ready(HealthyDatabase())

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "sector_snapshot_not_ready"


def test_readiness_returns_503_when_sector_snapshot_is_stale(monkeypatch):
    monkeypatch.setattr(app_module._SECTOR_REFRESH, "readiness", lambda: {"ok": False, "reason": "snapshot_stale"})

    with pytest.raises(HTTPException) as exc_info:
        app_module.ready(HealthyDatabase())

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["reason"] == "snapshot_stale"


def test_readiness_returns_503_when_public_dashboard_snapshot_is_missing(monkeypatch):
    monkeypatch.setattr(app_module._SECTOR_REFRESH, "readiness", lambda: {"ok": True})
    monkeypatch.setattr(app_module._PUBLIC_DATA_REFRESH, "readiness", lambda: {"ok": False, "reason": "snapshot_missing"})
    monkeypatch.setattr(app_module, "redis_ready", lambda: True)

    with pytest.raises(HTTPException) as exc_info:
        app_module.ready(HealthyDatabase())

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "public_data_snapshot_not_ready"
