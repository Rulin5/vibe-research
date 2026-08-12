"""pytest 配置：把 backend 目录加进 sys.path，注册 live 标记，隔离用户数据目录。"""
import os
import sys
import tempfile
from uuid import uuid4

import pytest

from test_database import resolve_test_database_url

sys.path.insert(0, os.path.dirname(__file__))

# Database-backed tests are never allowed to inherit the developer's application URL.
if os.environ.get("VR_TEST_DATABASE_URL"):
    os.environ["VR_DATABASE_URL"] = resolve_test_database_url()

# 用户数据隔离：portfolio / myreports 在 import 时按 VR_DATA_DIR / VR_REPORTS_DIR 固化路径，
# 必须赶在任何测试模块 import app 之前指到临时目录——否则持仓 CRUD 类测试会增删真实
# ~/.vibe-research/ 里的用户数据（比如把用户真实持有的 600519 合并后删掉）。
_TEST_DATA_DIR = tempfile.mkdtemp(prefix="vr-test-data-")
os.environ["VR_DATA_DIR"] = _TEST_DATA_DIR
os.environ["VR_REPORTS_DIR"] = os.path.join(_TEST_DATA_DIR, "myreports")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live: 打真实数据源的网络冒烟测（会联网、可能受上游/限流影响；默认可 -m 'not live' 跳过）",
    )


@pytest.fixture()
def authenticated_client():
    """A real session/CSRF client backed only by the guarded test database."""
    from fastapi.testclient import TestClient
    import app as app_module
    from db import get_session
    from models import User

    username = f"suite_{uuid4().hex[:16]}"
    client = TestClient(app_module.app)
    origin = "http://127.0.0.1:5900"
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "CorrectHorseBatteryStaple!9", "phone": "19198273569"},
        headers={"Origin": origin},
    )
    assert response.status_code == 201
    headers = {"Origin": origin, "X-CSRF-Token": client.cookies.get("vr_csrf", "")}
    try:
        yield client, headers
    finally:
        session = next(get_session())
        try:
            user = session.query(User).filter(User.username == username).one_or_none()
            if user is not None:
                session.delete(user)
                session.commit()
        finally:
            session.close()
