from sector_refresh import SectorRefreshService
from sector_snapshot import SectorSnapshotStore


def test_refresh_start_is_idempotent_while_running(tmp_path):
    service = SectorRefreshService(SectorSnapshotStore(tmp_path), builder=lambda date: ({}, {}))
    service._thread = object()
    service._state = {"task_id": "task-1", "status": "running"}

    first = service.start("request-1")

    assert first["task_id"] == "task-1"
    assert first["status"] == "running"


def test_failed_refresh_preserves_current_snapshot(tmp_path):
    store = SectorSnapshotStore(tmp_path)
    store.publish({"snapshot_id": "old", "status": "completed", "sectors": []})
    service = SectorRefreshService(
        store,
        builder=lambda date: (_ for _ in ()).throw(RuntimeError("upstream failure")),
        trade_dates=lambda: ["20260811"],
    )

    state = service.run_once("request-1")

    assert state["status"] == "failed"
    assert store.load_current()["snapshot_id"] == "old"


def test_refresh_limits_trade_date_fallback_attempts(tmp_path):
    attempted_dates = []

    def builder(trade_date):
        attempted_dates.append(trade_date)
        raise RuntimeError("not ready")

    service = SectorRefreshService(
        SectorSnapshotStore(tmp_path), builder=builder,
        trade_dates=lambda: ["20260811", "20260810", "20260807", "20260806"],
    )

    assert service.run_once("request-1")["status"] == "failed"
    assert attempted_dates == ["20260811", "20260810", "20260807"]
