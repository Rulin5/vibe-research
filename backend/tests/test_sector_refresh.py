from sector_refresh import SectorRefreshService
from sector_snapshot import SectorSnapshotStore
import sector_bootstrap
import sector_scheduler


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


def test_readiness_rejects_missing_snapshot(tmp_path):
    service = SectorRefreshService(SectorSnapshotStore(tmp_path))

    assert service.readiness()["reason"] == "snapshot_missing"


def test_readiness_serves_complete_snapshot_older_than_three_calendar_days_as_stale(tmp_path, monkeypatch):
    store = SectorSnapshotStore(tmp_path)
    store.publish({
        "snapshot_id": "old", "status": "completed", "as_of": "20260801",
        "retrieved_at": "2026-08-01T15:00:00+08:00",
        "sectors": [{"kind": "行业", "code": "881101.TI"}],
    })
    service = SectorRefreshService(store)
    monkeypatch.setattr("sector_refresh._today", lambda: __import__("datetime").date(2026, 8, 11))

    readiness = service.readiness()

    assert readiness["ok"] is True
    assert readiness["stale"] is True


def test_bootstrap_exits_successfully_when_verified_snapshot_is_ready(monkeypatch):
    class ReadyService:
        def readiness(self):
            return {"ok": True, "snapshot_id": "existing"}

    monkeypatch.setattr(sector_bootstrap, "SectorRefreshService", ReadyService)

    assert sector_bootstrap.main() == 0


def test_bootstrap_returns_failure_when_refresh_cannot_publish_snapshot(monkeypatch):
    class FailedService:
        def readiness(self):
            return {"ok": False, "reason": "snapshot_missing"}

        def run_once(self, _request_id):
            return {"status": "failed"}

    monkeypatch.setattr(sector_bootstrap, "SectorRefreshService", FailedService)

    assert sector_bootstrap.main() == 1


def test_bootstrap_refreshes_a_stale_snapshot_before_api_startup(monkeypatch):
    states = iter([
        {"ok": False, "reason": "snapshot_stale"},
        {"ok": True, "snapshot_id": "fresh"},
    ])

    class StaleService:
        def readiness(self):
            return next(states)

        def run_once(self, request_id):
            assert request_id == "api-startup-sector-bootstrap"
            return {"status": "completed"}

    monkeypatch.setattr(sector_bootstrap, "SectorRefreshService", StaleService)

    assert sector_bootstrap.ensure_ready("api-startup-sector-bootstrap") is None


def test_scheduler_refreshes_when_current_snapshot_is_not_ready(monkeypatch):
    calls = []

    class StaleService:
        def readiness(self):
            return {"ok": False, "reason": "snapshot_stale"}

        def run_once(self, request_id):
            calls.append(request_id)
            return {"status": "completed"}

    monkeypatch.setattr(sector_scheduler, "SectorRefreshService", StaleService)

    assert sector_scheduler.refresh_if_needed() == {"status": "completed"}
    assert calls == ["scheduled-sector-refresh"]


def test_scheduler_refreshes_summary_even_when_snapshot_has_latest_trade_date(monkeypatch):
    calls = []

    class ReadyService:
        def readiness(self):
            return {"ok": True, "snapshot_id": "fresh", "as_of": "20260811"}

        def trade_dates(self):
            return ["20260811"]

        def run_once(self, _request_id):
            calls.append(_request_id)
            return {"status": "completed"}

    monkeypatch.setattr(sector_scheduler, "SectorRefreshService", ReadyService)

    assert sector_scheduler.refresh_if_needed()["status"] == "completed"
    assert calls == ["scheduled-sector-refresh"]


def test_sector_scheduler_defaults_to_five_minutes():
    assert sector_scheduler.DEFAULT_INTERVAL_SECONDS == 300


def test_scheduler_refreshes_when_snapshot_is_not_latest_open_trade_date(monkeypatch):
    calls = []

    class YesterdayService:
        def readiness(self):
            return {"ok": True, "snapshot_id": "yesterday", "as_of": "20260810"}

        def trade_dates(self):
            return ["20260811", "20260810"]

        def run_once(self, request_id):
            calls.append(request_id)
            return {"status": "completed"}

    monkeypatch.setattr(sector_scheduler, "SectorRefreshService", YesterdayService)

    assert sector_scheduler.refresh_if_needed() == {"status": "completed"}
    assert calls == ["scheduled-sector-refresh"]


def test_refresh_skips_when_another_process_holds_the_shared_lock(tmp_path):
    store = SectorSnapshotStore(tmp_path)
    service = SectorRefreshService(store, trade_dates=lambda: ["20260811"])
    lock = store.try_acquire_refresh_lock()

    state = service.run_once("request-1")

    assert state["status"] == "skipped"
    assert state["current_step"] == "already_running"
    store.release_refresh_lock(lock)
