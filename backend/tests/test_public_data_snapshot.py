import pytest

from public_data_snapshot import PublicDataSnapshotStore


def complete_payload(snapshot_id="public-1"):
    symbols = [
        "CN.SH.000001", "CN.SZ.399001", "CN.SZ.399006", "CN.SH.000300",
        "GLOBAL.DJI", "GLOBAL.SPX", "GLOBAL.IXIC", "GLOBAL.HSI", "GLOBAL.HKTECH",
    ]
    return {
        "snapshot_id": snapshot_id,
        "status": "completed",
        "retrieved_at": "2026-08-12T10:00:00+08:00",
        "datasets": {
            "indices": [{"name": name} for name in ("上证指数", "深证成指", "创业板指", "沪深300")],
            "global_indices": [{"key": key} for key in ("dji", "spx", "ndx", "hsi", "hstech")],
            "market_overview": {"sentiment": {"up": 1}, "sectors": [{"name": "银行"}]},
            "market_emotion": {"date": "2026-08-12"},
            "turnover_top": {"stocks": [{"code": "600000"}]},
            "index_candles": [{"symbol": symbol, "candles": [{"close": 1}]} for symbol in symbols],
        },
    }


def test_store_publishes_only_complete_dashboard_snapshot(tmp_path):
    store = PublicDataSnapshotStore(tmp_path)

    store.publish(complete_payload())

    assert store.load_current()["snapshot_id"] == "public-1"


def test_store_rejects_missing_or_empty_required_dataset(tmp_path):
    store = PublicDataSnapshotStore(tmp_path)
    payload = complete_payload()
    payload["datasets"]["indices"] = []

    with pytest.raises(ValueError, match="indices"):
        store.publish(payload)

    assert store.load_current() is None


def test_failed_candidate_never_replaces_previous_snapshot(tmp_path):
    store = PublicDataSnapshotStore(tmp_path)
    store.publish(complete_payload("stable"))
    broken = complete_payload("broken")
    broken["datasets"]["market_emotion"] = {}

    with pytest.raises(ValueError):
        store.publish(broken)

    assert store.load_current()["snapshot_id"] == "stable"


def test_store_rejects_snapshot_with_an_empty_visible_subsection(tmp_path):
    store = PublicDataSnapshotStore(tmp_path)
    payload = complete_payload()
    payload["datasets"]["market_overview"]["sectors"] = []

    with pytest.raises(ValueError, match="market_overview.sectors"):
        store.publish(payload)


def test_store_rejects_snapshot_missing_any_dashboard_index(tmp_path):
    store = PublicDataSnapshotStore(tmp_path)
    payload = complete_payload()
    payload["datasets"]["index_candles"].pop()

    with pytest.raises(ValueError, match="index_candles.symbols"):
        store.publish(payload)
