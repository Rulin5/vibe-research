"""Stable application shapes for the global TeaJoin A-share adapter."""
import teajoin_data


def test_kline_normalizes_and_sorts_rows(monkeypatch):
    monkeypatch.setattr(teajoin_data.teajoin, "call", lambda api, params, fields="": [
        {"trade_date": "20260812", "open": 10, "high": 12, "low": 9, "close": 11, "pre_close": 10, "pct_chg": 10, "vol": 2, "amount": 3},
        {"trade_date": "20260811", "open": 9, "high": 10, "low": 8, "close": 10, "pre_close": 9, "pct_chg": 11.1, "vol": 1, "amount": 2},
    ])
    rows = teajoin_data.kline("600519", offset=2)
    assert [row["date"] for row in rows] == ["2026-08-11", "2026-08-12"]
    assert rows[-1]["source"] == "TeaJoin/Tushare daily"


def test_financials_combines_indicator_and_income(monkeypatch):
    def fake_call(api, params, fields=""):
        if api == "fina_indicator":
            return [{"end_date": "20260331", "eps": 2, "bps": 5, "ocfps": 1, "roe": 10, "grossprofit_margin": 40, "netprofit_margin": 20, "tr_yoy": 8, "netprofit_yoy": 9}]
        assert api == "income"
        return [{"end_date": "20260331", "total_revenue": 100, "n_income_attr_p": 20, "basic_eps": 2}]
    monkeypatch.setattr(teajoin_data.teajoin, "call", fake_call)
    data = teajoin_data.financials("600519")
    assert data["period"] == "2026-03-31"
    assert data["revenue"] == "100.00"
    assert data["source"] == "TeaJoin/Tushare fina_indicator + income"


def test_moneyflow_converts_thousand_yuan_to_yuan(monkeypatch):
    monkeypatch.setattr(teajoin_data.teajoin, "call", lambda *args, **kwargs: [{
        "trade_date": "20260812", "net_mf_amount": 12.5,
        "buy_sm_amount": 2, "sell_sm_amount": 1,
        "buy_md_amount": 4, "sell_md_amount": 2,
        "buy_lg_amount": 8, "sell_lg_amount": 3,
        "buy_elg_amount": 10, "sell_elg_amount": 4,
    }])
    row = teajoin_data.fund_flow("600519")[0]
    assert row["main_net"] == 125000
    assert row["super_net"] == 60000


def test_dividend_returns_per_ten_share_values(monkeypatch):
    monkeypatch.setattr(teajoin_data.teajoin, "call", lambda *args, **kwargs: [{
        "end_date": "20251231", "cash_div_tax": 2.5, "stk_co_rate": .1, "stk_bo_rate": .2, "div_proc": "实施",
    }])
    row = teajoin_data.dividend_history("600519")[0]
    assert row["bonus_rmb"] == 25
    assert row["transfer_ratio"] == 1
    assert row["bonus_ratio"] == 2
