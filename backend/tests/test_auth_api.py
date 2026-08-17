"""Authentication, session, and CSRF contracts against the local PostgreSQL database."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

import app as app_module
from db import get_session
from models import User


ORIGIN = "http://127.0.0.1:5900"


def _credentials() -> dict[str, str]:
    return {"username": f"test_{uuid4().hex[:16]}", "password": "CorrectHorseBatteryStaple!9", "phone": "19198273569"}


def _delete_user(username: str) -> None:
    session = next(get_session())
    try:
        user = session.query(User).filter(User.username == username).one_or_none()
        if user is not None:
            session.delete(user)
            session.commit()
    finally:
        session.close()


def test_register_hashes_password_and_establishes_cookie_session():
    credentials = _credentials()
    client = TestClient(app_module.app)
    try:
        response = client.post("/api/auth/register", json=credentials, headers={"Origin": ORIGIN})

        assert response.status_code == 201
        assert response.json()["data"]["username"] == credentials["username"]
        set_cookie = response.headers.get("set-cookie", "").lower()
        assert "vr_session=" in set_cookie
        assert "httponly" in set_cookie
        assert "samesite=lax" in set_cookie
        assert client.get("/api/auth/me").json()["data"]["username"] == credentials["username"]

        session = next(get_session())
        try:
            user = session.query(User).filter(User.username == credentials["username"]).one()
            assert user.password_hash != credentials["password"]
            assert user.password_hash.startswith("$argon2id$")
        finally:
            session.close()
    finally:
        _delete_user(credentials["username"])


def test_login_rejects_wrong_password_and_logout_revokes_session_with_csrf():
    credentials = _credentials()
    client = TestClient(app_module.app)
    try:
        assert client.post("/api/auth/register", json=credentials, headers={"Origin": ORIGIN}).status_code == 201
        assert client.post(
            "/api/auth/login",
            json={"username": credentials["username"], "password": "totally-wrong-password"},
            headers={"Origin": ORIGIN},
        ).status_code == 401

        assert client.post("/api/auth/logout", headers={"Origin": ORIGIN}).status_code == 403
        csrf = client.cookies.get("vr_csrf")
        response = client.post("/api/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
        assert response.status_code == 204
        assert client.get("/api/auth/me").status_code == 401
    finally:
        _delete_user(credentials["username"])


def test_wildcard_credential_cors_configuration_is_rejected():
    assert app_module.parse_allowed_origins("http://127.0.0.1:5900") == [ORIGIN]
    try:
        app_module.parse_allowed_origins("*")
    except RuntimeError as exc:
        assert "VR_ALLOW_ORIGINS" in str(exc)
    else:
        raise AssertionError("credentialed CORS must not accept a wildcard origin")


def test_register_accepts_chinese_username_phone_and_11_digit_password():
    username = f"清数_{uuid4().hex[:12]}"
    credentials = {"username": username, "password": "19198273569", "phone": "19198273569"}
    client = TestClient(app_module.app)
    try:
        response = client.post("/api/auth/register", json=credentials, headers={"Origin": ORIGIN})
        assert response.status_code == 201
        assert response.json()["data"]["username"] == username
        assert client.post("/api/auth/login", json={"username": username, "password": "19198273569"}, headers={"Origin": ORIGIN}).status_code == 200
    finally:
        _delete_user(username)
