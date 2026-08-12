"""我的研报 + 安全守卫（SSRF / 成本负数 / 日期）回归测。全部离线、不联网。

覆盖 2026-07-07 粉丝反馈批量修复中新增/加固的后端面：
- myreports：文件名分行业、存取删、类型白名单、data:URI 守卫、原子写。
- chat._check_base_url：防 SSRF（本地放行本机、始终挡云元数据、公网姿态挡内网）。
- 成本允许负数、清仓日期格式校验。
"""
import base64
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app as app_module
import chat
import myreports as mr
from db import get_session
from models import User

ORIGIN = "http://127.0.0.1:5900"


@pytest.fixture()
def private_client():
    username = f"report_{uuid4().hex[:16]}"
    client = TestClient(app_module.app)
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "CorrectHorseBatteryStaple!9", "phone": "19198273569"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 201
    try:
        yield client
    finally:
        session = next(get_session())
        try:
            user = session.query(User).filter(User.username == username).one_or_none()
            if user is not None:
                session.delete(user)
                session.commit()
        finally:
            session.close()


def _write_headers(client: TestClient) -> dict[str, str]:
    return {"Origin": ORIGIN, "X-CSRF-Token": client.cookies.get("vr_csrf", "")}

_B64 = "data:application/pdf;base64," + base64.b64encode(b"%PDF-1.4 test").decode()


# ---- 我的研报 ----

def test_classify_by_filename():
    assert mr.classify("东吴证券_中际旭创_光模块深度.pdf") == "光互联"
    assert mr.classify("宇树科技_人形机器人.pdf") == "人形机器人"
    assert mr.classify("随手记.txt") == "未分类"


def test_report_roundtrip_and_delete(tmp_path, monkeypatch, private_client):
    monkeypatch.setenv("VR_REPORTS_DIR", str(tmp_path))
    headers = _write_headers(private_client)
    r = private_client.post("/api/myreports", json={"name": "长鑫_HBM_深度.pdf", "content_b64": _B64}, headers=headers)
    assert r.status_code == 201
    meta = r.json()["data"]
    assert meta["industry"] == "未分类"
    rid = meta["id"]
    try:
        assert any(x["id"] == rid for x in private_client.get("/api/myreports").json()["data"])
        assert private_client.get(f"/api/myreports/file/{rid}").status_code == 200
    finally:
        assert private_client.delete(f"/api/myreports/{rid}", headers=headers).status_code == 204
    assert private_client.get(f"/api/myreports/file/{rid}").status_code == 404


def test_report_illegal_type_400(private_client):
    r = private_client.post("/api/myreports", json={"name": "x.exe", "content_b64": _B64}, headers=_write_headers(private_client))
    assert r.status_code == 400


def test_report_data_uri_without_comma_400(private_client):
    # 之前会 IndexError→500，现应 400
    assert private_client.post("/api/myreports", json={"name": "a.pdf", "content_b64": "data:"}, headers=_write_headers(private_client)).status_code == 400


def test_report_missing_file_404(private_client):
    assert private_client.get("/api/myreports/file/does-not-exist").status_code == 404


# ---- SSRF 守卫 ----

def _allowed(url: str) -> bool:
    try:
        chat._check_base_url(url)
        return True
    except RuntimeError:
        return False


def test_ssrf_local_mode(monkeypatch):
    monkeypatch.setenv("VR_DEPLOYMENT_MODE", "local")
    assert _allowed("https://api.deepseek.com") is True
    assert _allowed("http://127.0.0.1:11434") is True   # 本机 Ollama 等，本地放行
    assert _allowed("http://169.254.169.254/latest") is False  # 云元数据，始终挡
    assert _allowed("ftp://evil/x") is False


def test_ssrf_public_mode_blocks_internal(monkeypatch):
    monkeypatch.setenv("VR_DEPLOYMENT_MODE", "public")
    monkeypatch.setenv("VR_AI_ALLOWED_HOSTS", "api.stepfun.com")
    assert _allowed("http://192.168.1.1") is False
    assert _allowed("http://10.0.0.5") is False
    assert _allowed("http://127.0.0.1:11434") is False
    # 注：公网域名在 public 姿态会走真实 DNS 解析核对，为保持离线不在此断言


# ---- 成本负数 / 日期 ----

def test_negative_cost_accepted(private_client):
    headers = _write_headers(private_client)
    r = private_client.post("/api/portfolio/holding", json={"code": "600519", "shares": 100, "cost": -5.5}, headers=headers)
    assert r.status_code == 201
    assert private_client.delete(f"/api/portfolio/holding/{r.json()['data']['id']}", headers=headers).status_code == 204


def test_zero_shares_rejected(private_client):
    assert private_client.post("/api/portfolio/holding", json={"code": "600519", "shares": 0, "cost": 10}, headers=_write_headers(private_client)).status_code == 422


def test_close_bad_date_400(private_client):
    r = private_client.post("/api/portfolio/close",
                    json={"code": "600519", "date": "2025-13-45", "price": 10, "shares": 100, "cost": 5}, headers=_write_headers(private_client))
    assert r.status_code == 422
