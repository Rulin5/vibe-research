"""板块验证快照的单任务刷新编排。"""
from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import astock
import teajoin
from sector_snapshot import SectorSnapshotStore

_BEIJING = timezone(timedelta(hours=8))
MAX_TRADE_DATE_ATTEMPTS = 3


def _now() -> str:
    return datetime.now(_BEIJING).isoformat(timespec="seconds")


def _today():
    return datetime.now(_BEIJING).date()


def default_store() -> SectorSnapshotStore:
    return SectorSnapshotStore(Path(os.environ.get("VR_DATA_DIR") or Path.home() / ".vibe-research"))


def default_trade_dates() -> list[str]:
    today = datetime.now(_BEIJING).date()
    rows = teajoin.call(
        "trade_cal",
        {
            "exchange": "SSE",
            "start_date": (today - timedelta(days=21)).strftime("%Y%m%d"),
            "end_date": today.strftime("%Y%m%d"),
            "is_open": "1",
        },
        "cal_date,is_open",
    )
    return sorted(
        {str(row.get("cal_date") or "") for row in rows if str(row.get("is_open")) == "1"},
        reverse=True,
    )


class SectorRefreshService:
    def __init__(
        self,
        store: SectorSnapshotStore | None = None,
        builder: Callable[[str], tuple[dict, dict]] = astock.build_verified_sector_snapshot,
        trade_dates: Callable[[], list[str]] = default_trade_dates,
    ):
        self.store = store or default_store()
        self.builder = builder
        self.trade_dates = trade_dates
        self._lock = threading.RLock()
        self._thread: threading.Thread | object | None = None
        self._state = self.store.load_refresh_state() or {"status": "idle"}

    def _save(self, **updates) -> dict:
        self._state = {**self._state, **updates, "updated_at": _now()}
        self.store.save_refresh_state(self._state)
        return dict(self._state)

    def status(self) -> dict:
        with self._lock:
            return dict(self._state)

    def readiness(self) -> dict:
        """A complete last-known snapshot stays readable while refresh catches up."""
        snapshot = self.store.load_current()
        if snapshot is None:
            return {"ok": False, "reason": "snapshot_missing"}
        sectors = snapshot.get("sectors")
        if not isinstance(sectors, list) or not sectors:
            return {"ok": False, "reason": "snapshot_empty", "snapshot_id": snapshot.get("snapshot_id")}
        as_of = str(snapshot.get("as_of") or "")
        try:
            snapshot_date = datetime.strptime(as_of, "%Y%m%d").date()
        except ValueError:
            return {"ok": False, "reason": "snapshot_invalid", "snapshot_id": snapshot.get("snapshot_id")}
        age_days = (_today() - snapshot_date).days
        if age_days < 0:
            return {"ok": False, "reason": "snapshot_invalid", "snapshot_id": snapshot.get("snapshot_id")}
        retrieved_at = str(snapshot.get("retrieved_at") or "")
        try:
            retrieved = datetime.fromisoformat(retrieved_at)
            age_seconds = max(0, int((datetime.now(_BEIJING) - retrieved).total_seconds()))
        except ValueError:
            age_seconds = None
        stale = age_days > 3 or age_seconds is None or age_seconds > 300
        return {
            "ok": True, "stale": stale, "age_seconds": age_seconds,
            "snapshot_id": snapshot.get("snapshot_id"), "as_of": as_of, "retrieved_at": retrieved_at,
        }

    def start(self, request_id: str) -> dict:
        with self._lock:
            if self._state.get("status") in {"pending", "running"} and self._thread is not None:
                return dict(self._state)
            task_id = uuid.uuid4().hex
            self._save(
                task_id=task_id, request_id=request_id, status="pending", current_step="queued",
                attempts=0, started_at=_now(), ended_at=None, error_type=None, error_detail=None,
            )
            self._thread = threading.Thread(target=self.run_once, args=(request_id,), daemon=True, name="sector-refresh")
            self._thread.start()
            return dict(self._state)

    def run_once(self, request_id: str) -> dict:
        refresh_lock = self.store.try_acquire_refresh_lock()
        if refresh_lock is None:
            # Never overwrite state owned by the process that currently holds the lock.
            return {"status": "skipped", "current_step": "already_running"}
        with self._lock:
            task_id = self._state.get("task_id") or uuid.uuid4().hex
            self._save(task_id=task_id, request_id=request_id, status="running", current_step="resolving_trade_date", attempts=1)
        try:
            dates = self.trade_dates()
            if not dates:
                raise RuntimeError("no open trade date returned")
            last_error: Exception | None = None
            for trade_date in dates[:MAX_TRADE_DATE_ATTEMPTS]:
                try:
                    with self._lock:
                        self._save(status="running", current_step=f"validating_{trade_date}", data_date=trade_date)
                    current = self.store.load_current()
                    reusable_members = None
                    if current and current.get("as_of") == trade_date:
                        reusable_members = self.store.load_all_members(str(current.get("snapshot_id") or ""))
                    if self.builder is astock.build_verified_sector_snapshot:
                        snapshot, members = self.builder(trade_date, reusable_members=reusable_members)
                    else:
                        snapshot, members = self.builder(trade_date)
                    kinds = {row.get("kind") for row in snapshot.get("sectors", [])}
                    if not {"行业", "概念"}.issubset(kinds):
                        raise RuntimeError("daily snapshot does not contain validated industry and concept data")
                    self.store.publish(snapshot, members)
                    with self._lock:
                        return self._save(
                            status="completed", current_step="published", ended_at=_now(),
                            snapshot_id=snapshot["snapshot_id"], data_date=trade_date,
                            completeness=snapshot.get("completeness"),
                        )
                except Exception as exc:  # try the preceding open day only when current data is not ready
                    last_error = exc
            raise last_error or RuntimeError("no valid sector snapshot")
        except Exception as exc:
            with self._lock:
                return self._save(
                    status="failed", current_step="failed", ended_at=_now(),
                    error_type=type(exc).__name__, error_detail=str(exc)[:500],
                )
        finally:
            self.store.release_refresh_lock(refresh_lock)
