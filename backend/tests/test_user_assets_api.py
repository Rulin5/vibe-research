"""Private user assets must never cross the authenticated user boundary."""

from __future__ import annotations

import base64
from uuid import uuid4

from fastapi.testclient import TestClient

import app as app_module
from db import get_session
from models import User


ORIGIN = "http://127.0.0.1:5900"
PDF_B64 = "data:application/pdf;base64," + base64.b64encode(b"%PDF-1.4 private test").decode()


def _register() -> tuple[TestClient, str]:
    username = f"asset_{uuid4().hex[:16]}"
    client = TestClient(app_module.app)
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "CorrectHorseBatteryStaple!9", "phone": "19198273569"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 201
    return client, username


def _write_headers(client: TestClient) -> dict[str, str]:
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


def test_private_assets_are_scoped_to_the_authenticated_user(tmp_path, monkeypatch):
    monkeypatch.setenv("VR_REPORTS_DIR", str(tmp_path))
    client_a, username_a = _register()
    client_b, username_b = _register()
    try:
        assert client_a.get("/api/watchlist").status_code == 200
        assert client_a.post("/api/watchlist", json={"code": "600519"}, headers=_write_headers(client_a)).status_code == 201
        assert client_a.post("/api/watchlist", json={"code": "600519"}, headers=_write_headers(client_a)).status_code == 200

        holding = client_a.post(
            "/api/portfolio/holding", json={"code": "600519", "shares": 100, "cost": 1500.25}, headers=_write_headers(client_a)
        )
        assert holding.status_code == 201
        holding_id = holding.json()["data"]["id"]

        note = client_a.post(
            "/api/notes", json={"title": "A 的研究", "content": "仅 A 可见", "kind": "daily-review"}, headers=_write_headers(client_a)
        )
        assert note.status_code == 201
        note_id = note.json()["data"]["id"]
        assert note.json()["data"]["kind"] == "daily-review"

        report = client_a.post(
            "/api/myreports", json={"name": "A-private.pdf", "content_b64": PDF_B64}, headers=_write_headers(client_a)
        )
        assert report.status_code == 201
        report_id = report.json()["data"]["id"]

        assert client_b.get("/api/watchlist").json()["data"] == []
        assert client_b.get("/api/portfolio").json()["data"]["holdings"] == []
        assert client_b.get("/api/notes").json()["data"] == []
        assert client_b.get("/api/myreports").json()["data"] == []

        assert client_b.delete(f"/api/portfolio/holding/{holding_id}", headers=_write_headers(client_b)).status_code == 404
        assert client_b.delete(f"/api/notes/{note_id}", headers=_write_headers(client_b)).status_code == 404
        assert client_b.get(f"/api/myreports/file/{report_id}").status_code == 404
        assert client_b.delete(f"/api/myreports/{report_id}", headers=_write_headers(client_b)).status_code == 404

        assert (tmp_path / client_a.get("/api/auth/me").json()["data"]["id"] / f"{report_id}.pdf").exists()
    finally:
        _delete_user(username_a)
        _delete_user(username_b)


def test_private_assets_require_authentication_and_csrf():
    client = TestClient(app_module.app)
    assert client.get("/api/portfolio").status_code == 401
    assert client.post("/api/watchlist", json={"code": "600519"}).status_code == 401


def test_portfolio_keeps_individual_lots_and_marks_quote_data_source(monkeypatch):
    client, username = _register()
    monkeypatch.setattr(
        app_module.user_assets.astock,
        "tencent_quote",
        lambda codes: {code: {"name": f"证券{code}", "price": 10.5} for code in codes},
    )
    try:
        headers = _write_headers(client)
        first = client.post(
            "/api/portfolio/holding", json={"code": "600519", "shares": 100, "cost": 8}, headers=headers
        )
        second = client.post(
            "/api/portfolio/holding", json={"code": "600519", "shares": 50, "cost": 9}, headers=headers
        )
        assert first.status_code == 201
        assert second.status_code == 201

        holdings = client.get("/api/portfolio").json()["data"]["holdings"]
        assert len(holdings) == 2
        assert len({holding["id"] for holding in holdings}) == 2
        assert all(holding["quote_status"] == "available" for holding in holdings)
        assert all(holding["price"] == 10.5 for holding in holdings)
        assert client.delete(f"/api/portfolio/holding/{holdings[0]['id']}", headers=headers).status_code == 204
        assert len(client.get("/api/portfolio").json()["data"]["holdings"]) == 1
    finally:
        _delete_user(username)
