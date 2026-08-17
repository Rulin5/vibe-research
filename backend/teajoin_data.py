"""TeaJoin-backed A-share adapters with stable application-facing shapes."""
from __future__ import annotations

import math
import time
from datetime import date, datetime, timedelta
from threading import RLock
from typing import Any, Callable

import teajoin

_LOCK = RLock()
_CACHE: dict[tuple[Any, ...], tuple[float, Any]] = {}


def _cached(key: tuple[Any, ...], ttl: int, loader: Callable[[], Any]) -> Any:
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
    value = loader()
    with _LOCK:
        _CACHE[key] = (time.time(), value)
    return value


def ts_code(code: str) -> str:
    suffix = "SH" if code.startswith(("5", "6", "9")) else "BJ" if code.startswith(("4", "8")) else "SZ"
    return f"{code}.{suffix}"


def compact_date(value: Any) -> str:
    text = str(value or "")[:8]
    return f"{text[:4]}-{text[4:6]}-{text[6:8]}" if len(text) == 8 else text


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _human_cny(value: Any) -> str | None:
    if value in (None, ""):
        return None
    number = _number(value, float("nan"))
    if not math.isfinite(number):
        return None
    if abs(number) >= 100_000_000:
        return f"{number / 100_000_000:.2f}亿"
    if abs(number) >= 10_000:
        return f"{number / 10_000:.2f}万"
    return f"{number:.2f}"


def _range(days: int) -> tuple[str, str]:
    end = date.today()
    return (end - timedelta(days=days)).strftime("%Y%m%d"), end.strftime("%Y%m%d")


def stock_profile(code: str) -> dict:
    rows = teajoin.call(
        "stock_basic", {"ts_code": ts_code(code), "list_status": "L"},
        "ts_code,symbol,name,area,industry,market,list_date,act_name,act_ent_type",
    )
    if not rows:
        return {}
    row = rows[0]
    return {
        "股票代码": row.get("symbol") or code,
        "股票简称": row.get("name"),
        "总股本": None,
        "流通股": None,
        "行业": row.get("industry"),
        "上市时间": compact_date(row.get("list_date")),
        "地区": row.get("area"),
        "市场": row.get("market"),
        "实控人": row.get("act_name"),
        "实控人类型": row.get("act_ent_type"),
        "source": "TeaJoin/Tushare stock_basic",
    }


def kline(code: str, category: int = 4, offset: int = 60) -> list[dict]:
    api = {4: "daily", 5: "weekly", 6: "monthly"}.get(category)
    if api is None:
        raise ValueError("TeaJoin 通用套餐不提供分钟 K 线；category 仅支持 4(日)、5(周)、6(月)")
    days = max(offset * ({4: 2, 5: 10, 6: 45}[category]), 90)
    start, end = _range(days)
    rows = teajoin.call(api, {"ts_code": ts_code(code), "start_date": start, "end_date": end})
    normalized = [{
        "datetime": compact_date(row.get("trade_date")),
        "date": compact_date(row.get("trade_date")),
        "open": _number(row.get("open")), "high": _number(row.get("high")),
        "low": _number(row.get("low")), "close": _number(row.get("close")),
        "last_close": _number(row.get("pre_close")), "change": _number(row.get("change")),
        "change_pct": _number(row.get("pct_chg")), "volume": _number(row.get("vol")),
        "amount": _number(row.get("amount")), "source": f"TeaJoin/Tushare {api}",
    } for row in rows]
    normalized.sort(key=lambda row: row["date"])
    return normalized[-offset:]


def financials(code: str) -> dict:
    start, end = _range(700)
    params = {"ts_code": ts_code(code), "start_date": start, "end_date": end}
    indicators = teajoin.call(
        "fina_indicator", params,
        "ts_code,ann_date,end_date,eps,bps,ocfps,roe,grossprofit_margin,netprofit_margin,tr_yoy,netprofit_yoy",
    )
    incomes = teajoin.call("income", params, "ts_code,ann_date,end_date,total_revenue,n_income_attr_p,basic_eps")
    if not indicators and not incomes:
        return {}
    indicator = max(indicators, key=lambda row: str(row.get("end_date") or ""), default={})
    income = max(incomes, key=lambda row: str(row.get("end_date") or ""), default={})
    value = lambda v: None if v in (None, "") else v
    return {
        "period": compact_date(indicator.get("end_date") or income.get("end_date")),
        "revenue": _human_cny(income.get("total_revenue")), "revenue_yoy": value(indicator.get("tr_yoy")),
        "net_profit": _human_cny(income.get("n_income_attr_p")), "net_profit_yoy": value(indicator.get("netprofit_yoy")),
        "eps": value(indicator.get("eps") or income.get("basic_eps")), "bvps": value(indicator.get("bps")),
        "roe": value(indicator.get("roe")), "gross_margin": value(indicator.get("grossprofit_margin")),
        "net_margin": value(indicator.get("netprofit_margin")), "op_cf_ps": value(indicator.get("ocfps")),
        "source": "TeaJoin/Tushare fina_indicator + income",
    }


def valuation_percentile(code: str, years: int = 5) -> dict:
    start, end = _range(366 * years + 30)
    rows = teajoin.call("daily_basic", {"ts_code": ts_code(code), "start_date": start, "end_date": end}, "trade_date,pe_ttm,pb")

    def metric(field: str) -> dict | None:
        dated = sorted((str(row.get("trade_date") or ""), _number(row.get(field), float("nan"))) for row in rows)
        values = [value for _, value in dated if math.isfinite(value) and value > 0]
        if not values:
            return None
        current, ordered = values[-1], sorted(values)
        quantile = lambda p: ordered[min(round(p * (len(ordered) - 1)), len(ordered) - 1)]
        return {
            "current": round(current, 2), "percentile": round(sum(v < current for v in ordered) / max(len(ordered) - 1, 1) * 100, 1),
            "min": round(ordered[0], 2), "max": round(ordered[-1], 2), "p20": round(quantile(.2), 2),
            "p50": round(quantile(.5), 2), "p80": round(quantile(.8), 2), "n": len(ordered),
        }

    metrics = {name: value for name in ("pe_ttm", "pb") if (value := metric(name)) is not None}
    return {"period": f"近{years}年", "metrics": metrics, "source": "TeaJoin/Tushare daily_basic"}


def margin_trading(code: str, page_size: int = 30) -> list[dict]:
    start, end = _range(max(page_size * 3, 90))
    rows = teajoin.call("margin_detail", {"ts_code": ts_code(code), "start_date": start, "end_date": end})
    return [{"date": compact_date(r.get("trade_date")), **{k: _number(r.get(k)) for k in ("rzye", "rzmre", "rzche", "rqye", "rqmcl", "rzrqye")}} for r in rows[:page_size]]


def block_trade(code: str, page_size: int = 20) -> list[dict]:
    start, end = _range(730)
    rows = teajoin.call("block_trade", {"ts_code": ts_code(code), "start_date": start, "end_date": end})
    selected = rows[:page_size]
    trade_dates = [str(row.get("trade_date") or "") for row in selected if row.get("trade_date")]
    closes: dict[str, float] = {}
    if trade_dates:
        daily_rows = teajoin.call("daily", {"ts_code": ts_code(code), "start_date": min(trade_dates), "end_date": max(trade_dates)}, "trade_date,close")
        closes = {str(row.get("trade_date") or ""): _number(row.get("close")) for row in daily_rows}
    result = []
    for row in selected:
        day = str(row.get("trade_date") or "")
        price, close = _number(row.get("price")), closes.get(day, 0)
        result.append({"date": compact_date(day), "price": price, "close": close,
                       "premium_pct": round((price / close - 1) * 100, 2) if close else None,
                       "vol": _number(row.get("vol")) * 10_000, "amount": _number(row.get("amount")) * 10_000,
                       "buyer": row.get("buyer") or "", "seller": row.get("seller") or ""})
    return result


def holder_num_change(code: str, page_size: int = 10) -> list[dict]:
    start, end = _range(1200)
    rows = teajoin.call("stk_holdernumber", {"ts_code": ts_code(code), "start_date": start, "end_date": end})
    result = []
    for index, row in enumerate(rows[:page_size]):
        current = _number(row.get("holder_num"))
        previous = _number(rows[index + 1].get("holder_num")) if index + 1 < len(rows) else 0
        result.append({"date": compact_date(row.get("end_date")), "holder_num": current,
                       "change_ratio": round((current / previous - 1) * 100, 2) if previous else 0, "avg_shares": 0})
    return result


def dividend_history(code: str, page_size: int = 20) -> list[dict]:
    rows = teajoin.call("dividend", {"ts_code": ts_code(code)})
    return [{"date": compact_date(r.get("ex_date") or r.get("end_date")), "bonus_rmb": round(_number(r.get("cash_div_tax")) * 10, 4),
             "transfer_ratio": round(_number(r.get("stk_co_rate")) * 10, 4), "bonus_ratio": round(_number(r.get("stk_bo_rate")) * 10, 4),
             "plan": r.get("div_proc") or ""} for r in rows[:page_size]]


def fund_flow(code: str, limit: int = 120) -> list[dict]:
    start, end = _range(max(limit * 2, 250))
    rows = teajoin.call("moneyflow", {"ts_code": ts_code(code), "start_date": start, "end_date": end})
    result = []
    for r in rows[:limit]:
        # Tushare moneyflow amount fields are 万元; the frontend contract is 元.
        small = (_number(r.get("buy_sm_amount")) - _number(r.get("sell_sm_amount"))) * 10_000
        mid = (_number(r.get("buy_md_amount")) - _number(r.get("sell_md_amount"))) * 10_000
        large = (_number(r.get("buy_lg_amount")) - _number(r.get("sell_lg_amount"))) * 10_000
        super_net = (_number(r.get("buy_elg_amount")) - _number(r.get("sell_elg_amount"))) * 10_000
        result.append({"date": compact_date(r.get("trade_date")), "main_net": _number(r.get("net_mf_amount")) * 10_000,
                       "small_net": small, "mid_net": mid, "large_net": large, "super_net": super_net})
    result.sort(key=lambda row: row["date"])
    return result


def lockup_expiry(code: str, trade_date: str | None = None, forward_days: int = 90) -> dict:
    today = datetime.strptime(trade_date, "%Y-%m-%d").date() if trade_date else date.today()
    rows = teajoin.call("share_float", {"ts_code": ts_code(code), "start_date": (today - timedelta(days=730)).strftime("%Y%m%d"),
                                          "end_date": (today + timedelta(days=forward_days)).strftime("%Y%m%d")})
    normalized = [{"date": compact_date(r.get("float_date") or r.get("ann_date")), "type": r.get("holder_name") or "限售股解禁",
                   "shares": _number(r.get("float_share")) * 10000, "able_shares": _number(r.get("float_share")) * 10000, "ratio": 0} for r in rows]
    boundary = today.isoformat()
    return {"history": [r for r in normalized if r["date"] < boundary][:15], "upcoming": [r for r in normalized if r["date"] >= boundary][:20]}


def dragon_tiger(code: str, trade_date: str | None = None, look_back: int = 30) -> dict:
    end = datetime.strptime(trade_date, "%Y-%m-%d").date() if trade_date else date.today()
    records: list[dict] = []
    selected_day = ""
    selected_rows: list[dict] = []
    for back in range(look_back + 1):
        day = (end - timedelta(days=back)).strftime("%Y%m%d")
        rows = teajoin.call("top_list", {"trade_date": day})
        matched = [row for row in rows if str(row.get("ts_code") or "") == ts_code(code)]
        for row in matched:
            records.append({"date": compact_date(day), "reason": row.get("reason") or "",
                            "net_buy": round(_number(row.get("net_amount")) / 10000, 1),
                            "turnover": _number(row.get("turnover_rate"))})
        if matched and not selected_day:
            selected_day, selected_rows = day, matched
        if len(records) >= 12:
            break
    seats = {"buy": [], "sell": []}
    institution = {"buy_amt": 0.0, "sell_amt": 0.0, "net_amt": 0.0}
    if selected_day:
        details = teajoin.call("top_inst", {"trade_date": selected_day, "ts_code": ts_code(code)})
        normalized = []
        for row in details:
            item = {"name": row.get("exalter") or "", "buy_amt": round(_number(row.get("buy")) / 10000, 1),
                    "sell_amt": round(_number(row.get("sell")) / 10000, 1), "net": round(_number(row.get("net_buy")) / 10000, 1)}
            normalized.append(item)
            if "机构专用" in item["name"]:
                institution["buy_amt"] += item["buy_amt"]
                institution["sell_amt"] += item["sell_amt"]
        seats["buy"] = sorted(normalized, key=lambda row: row["buy_amt"], reverse=True)[:5]
        seats["sell"] = sorted(normalized, key=lambda row: row["sell_amt"], reverse=True)[:5]
        institution["net_amt"] = round(institution["buy_amt"] - institution["sell_amt"], 1)
    return {"records": records, "seats": seats, "institution": institution}


def report_forecast(code: str) -> list[dict]:
    start, end = _range(730)
    rows = teajoin.call("report_rc", {"ts_code": ts_code(code), "start_date": start, "end_date": end})
    return [row for row in rows if str(row.get("ts_code") or "") == ts_code(code) and row.get("report_type") == "个股"]


def profit_forecast(code: str) -> list[dict]:
    grouped: dict[str, list[float]] = {}
    for row in report_forecast(code):
        year = str(row.get("quarter") or "")[:4]
        eps = _number(row.get("eps"), float("nan"))
        if len(year) == 4 and year.isdigit() and math.isfinite(eps):
            grouped.setdefault(year, []).append(eps)
    return [{"年度": year, "均值": round(sum(values) / len(values), 4), "预测机构数": len(values)}
            for year, values in sorted(grouped.items())]
