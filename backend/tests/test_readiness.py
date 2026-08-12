import pytest
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

import app as app_module


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
