import pytest

from public_data_refresh import PublicDataRefreshService
from public_data_snapshot import PublicDataSnapshotStore


def collectors():
    symbols = [
        "CN.SH.000001", "CN.SZ.399001", "CN.SZ.399006", "CN.SH.000300",
        "GLOBAL.DJI", "GLOBAL.SPX", "GLOBAL.IXIC", "GLOBAL.HSI", "GLOBAL.HKTECH",
    ]
    return {
        "indices": lambda: [{"name": name} for name in ("上证指数", "深证成指", "创业板指", "沪深300")],
        "global_indices": lambda: [{"key": key} for key in ("dji", "spx", "ndx", "hsi", "hstech")],
        "market_overview": lambda: {"sentiment": {"up": 1}, "sectors": [{"name": "银行"}]},
        "market_emotion": lambda: {"date": "2026-08-12"},
        "turnover_top": lambda: {"stocks": [{"code": "600000"}]},
        "index_candles": lambda: [{"symbol": symbol, "candles": [{"close": 1}]} for symbol in symbols],
    }


def test_refresh_publishes_complete_snapshot(tmp_path):
    store = PublicDataSnapshotStore(tmp_path)
    service = PublicDataRefreshService(store=store, collectors=collectors())

    state = service.run_once("deploy-bootstrap")

    assert state["status"] == "completed"
    assert service.readiness()["ok"] is True


def test_refresh_failure_keeps_last_successful_snapshot_ready(tmp_path):
    store = PublicDataSnapshotStore(tmp_path)
    service = PublicDataRefreshService(store=store, collectors=collectors())
    assert service.run_once("first")["status"] == "completed"
    broken = collectors()
    broken["indices"] = lambda: (_ for _ in ()).throw(RuntimeError("upstream down"))

    state = PublicDataRefreshService(store=store, collectors=broken).run_once("scheduled")

    assert state["status"] == "failed"
    assert PublicDataRefreshService(store=store, collectors=broken).readiness()["ok"] is True
    assert store.load_current()["status"] == "completed"


def test_readiness_rejects_missing_snapshot(tmp_path):
    service = PublicDataRefreshService(store=PublicDataSnapshotStore(tmp_path), collectors=collectors())

    assert service.readiness() == {"ok": False, "reason": "snapshot_missing"}
