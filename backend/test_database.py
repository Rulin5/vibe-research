"""Fail-closed helpers for the disposable PostgreSQL test database."""

from __future__ import annotations

import os

from sqlalchemy.engine import make_url


TEST_DATABASE_ENV = "VR_TEST_DATABASE_URL"


def validate_test_database_url(value: str) -> str:
    candidate = (value or "").strip()
    try:
        parsed = make_url(candidate)
    except Exception as exc:
        raise RuntimeError(f"{TEST_DATABASE_ENV} is not a valid database URL") from exc
    if parsed.drivername != "postgresql+psycopg":
        raise RuntimeError(f"{TEST_DATABASE_ENV} must use postgresql+psycopg")
    if not parsed.database or not parsed.database.lower().endswith("_test"):
        raise RuntimeError(f"{TEST_DATABASE_ENV} database name must end with _test")
    return candidate


def resolve_test_database_url() -> str:
    return validate_test_database_url(os.environ.get(TEST_DATABASE_ENV, ""))
