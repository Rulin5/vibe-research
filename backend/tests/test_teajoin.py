"""TeaJoin/Tushare 适配器契约：密钥留在运行环境，失败不能伪装为空数据。"""
import pytest

import teajoin


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = "provider response"

    def json(self):
        return self._payload


def test_missing_key_is_a_configuration_error(monkeypatch):
    monkeypatch.delenv("TEAJOIN_API_KEY", raising=False)
    monkeypatch.setattr(teajoin, "_load_dotenv_key", lambda: "")
    with pytest.raises(teajoin.TeaJoinConfigError):
        teajoin.call("stock_basic")


def test_call_normalizes_tushare_fields_and_items(monkeypatch):
    monkeypatch.setenv("TEAJOIN_API_KEY", "test-key")
    monkeypatch.setattr(teajoin, "_wait_for_rate_limit", lambda: None)
    seen = {}

    def fake_post(url, *, json, timeout):
        seen.update({"url": url, "json": json, "timeout": timeout})
        return _Response({"code": 0, "data": {"fields": ["ts_code", "name"], "items": [["600519.SH", "贵州茅台"]]}})

    monkeypatch.setattr(teajoin.requests, "post", fake_post)
    assert teajoin.call("stock_basic", {"list_status": "L"}) == [{"ts_code": "600519.SH", "name": "贵州茅台"}]
    assert seen["url"] == "https://teajoin.com"
    assert seen["json"]["api_name"] == "stock_basic"
    assert seen["json"]["token"] == "test-key"
    assert seen["timeout"] == 15


def test_provider_failure_is_not_normalized_to_empty_rows(monkeypatch):
    monkeypatch.setenv("TEAJOIN_API_KEY", "test-key")
    monkeypatch.setattr(teajoin, "_wait_for_rate_limit", lambda: None)
    monkeypatch.setattr(teajoin.requests, "post", lambda *args, **kwargs: _Response({"code": -2001, "msg": "权限不足"}, 200))
    with pytest.raises(teajoin.TeaJoinUpstreamError, match="权限不足"):
        teajoin.call("ths_index")
