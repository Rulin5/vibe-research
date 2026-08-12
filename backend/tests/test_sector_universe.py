import astock
import teajoin


def test_verified_snapshot_uses_same_day_daily_industry_and_concept_sources(monkeypatch):
    def fake_call(api_name, params=None, fields=""):
        if api_name == "moneyflow_ind_ths":
            return [{
                "trade_date": "20260811", "ts_code": "881101.TI", "industry": "种植业与林业",
                "close": 4022.37, "pct_change": -1.32, "company_num": 1,
                "lead_stock": "示例行业股", "net_amount": 100.5,
            }]
        if api_name == "moneyflow_cnt_ths":
            return [{
                "trade_date": "20260811", "ts_code": "885001.TI", "name": "人工智能",
                "close_price": 2010.2, "pct_change": 1.23, "company_num": 1,
                "lead_stock": "示例概念股", "net_amount": -22.1,
            }]
        if api_name == "ths_member":
            return [{"con_code": "600000.SH", "con_name": "浦发银行", "in_date": "20200101", "out_date": ""}]
        raise AssertionError(api_name)

    monkeypatch.setattr(astock.teajoin, "call", fake_call)
    snapshot, members = astock.build_verified_sector_snapshot("20260811")

    assert snapshot["as_of"] == "20260811"
    assert snapshot["completeness"] == {
        "candidate_count": 2, "published_count": 2, "excluded_count": 0, "excluded_by_reason": {},
        "provider_row_counts": {"moneyflow_ind_ths": 1, "moneyflow_cnt_ths": 1},
    }
    assert {row["kind"] for row in snapshot["sectors"]} == {"行业", "概念"}
    assert all(row["close"] is not None and row["pct_change"] is not None for row in snapshot["sectors"])
    assert all(row["data_status"] == "complete" for row in snapshot["sectors"])
    assert all(members[(row["kind"], row["code"])] for row in snapshot["sectors"])


def test_verified_snapshot_excludes_daily_sector_without_constituents(monkeypatch):
    def fake_call(api_name, params=None, fields=""):
        if api_name == "moneyflow_ind_ths":
            return []
        if api_name == "moneyflow_cnt_ths":
            return [{
                "trade_date": "20260811", "ts_code": "886112.TI", "name": "无成分概念",
                "close_price": 100.0, "pct_change": 1.0, "company_num": 2,
                "lead_stock": "示例股", "net_amount": 2.0,
            }]
        if api_name == "ths_member":
            return []
        raise AssertionError(api_name)

    monkeypatch.setattr(astock.teajoin, "call", fake_call)
    snapshot, members = astock.build_verified_sector_snapshot("20260811")

    assert snapshot["sectors"] == []
    assert members == {}
    assert snapshot["completeness"]["candidate_count"] == 1
    assert snapshot["completeness"]["excluded_count"] == 1
    assert snapshot["completeness"]["excluded_by_reason"] == {"empty_members": 1}


def test_daily_industry_without_a_name_is_not_normalized():
    row = {
        "trade_date": "20260811", "ts_code": "881101.TI", "industry": None,
        "close": 1.0, "pct_change": 1.0, "company_num": 1, "lead_stock": "示例股", "net_amount": 1.0,
    }

    assert astock._normalized_daily_sector(row, "行业", "20260811", "moneyflow_ind_ths") is None


def test_member_fetch_retries_one_transient_teajoin_failure(monkeypatch):
    attempts = []

    def fake_call(api_name, params=None, fields=""):
        attempts.append(api_name)
        if len(attempts) == 1:
            try:
                raise OSError("connection reset")
            except OSError as cause:
                raise teajoin.TeaJoinUpstreamError("request failed") from cause
        return [{"con_code": "600000.SH", "con_name": "浦发银行", "in_date": "", "out_date": ""}]

    monkeypatch.setattr(astock.teajoin, "call", fake_call)
    monkeypatch.setattr(astock.time, "sleep", lambda seconds: None)

    assert astock._verified_ths_members("881101.TI", "20260811")[0]["code"] == "600000"
    assert attempts == ["ths_member", "ths_member"]
