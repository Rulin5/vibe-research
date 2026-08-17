"""Out-of-request collection and publication of public dashboard datasets."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import astock
import index_market
import market
from public_data_snapshot import PublicDataSnapshotStore


_BEIJING = timezone(timedelta(hours=8))
INDEX_SYMBOLS = (
    "CN.SH.000001", "CN.SZ.399001", "CN.SZ.399006", "CN.SH.000300",
    "GLOBAL.DJI", "GLOBAL.SPX", "GLOBAL.IXIC", "GLOBAL.HSI", "GLOBAL.HKTECH",
)


def default_store() -> PublicDataSnapshotStore:
    return PublicDataSnapshotStore(Path(os.environ.get("VR_DATA_DIR") or Path.home() / ".vibe-research"))


def default_collectors() -> dict[str, Callable[[], object]]:
    return {
        "indices": astock.index_quote,
        "global_indices": market.get_global_indices,
        "market_overview": market.get_overview,
        "market_emotion": market.get_short_term_emotion,
        "turnover_top": market.get_turnover_top,
        "index_candles": lambda: index_market.get_index_series_batch(list(INDEX_SYMBOLS), limit=60),
    }


class PublicDataRefreshService:
    def __init__(self, store: PublicDataSnapshotStore | None = None, collectors: dict[str, Callable[[], object]] | None = None):
        self.store = store or default_store()
        self.collectors = collectors or default_collectors()

    def readiness(self) -> dict:
        snapshot = self.store.load_current()
        if snapshot is None:
            return {"ok": False, "reason": "snapshot_missing"}
        return {
            "ok": True, "snapshot_id": snapshot["snapshot_id"],
            "retrieved_at": snapshot["retrieved_at"],
        }

    def run_once(self, request_id: str) -> dict:
        refresh_lock = self.store.try_acquire_refresh_lock()
        if refresh_lock is None:
            return {"status": "skipped", "current_step": "already_running", "request_id": request_id}
        try:
            datasets = {name: collector() for name, collector in self.collectors.items()}
            snapshot = {
                "snapshot_id": f"{datetime.now(_BEIJING).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}",
                "status": "completed", "retrieved_at": datetime.now(_BEIJING).isoformat(timespec="seconds"),
                "request_id": request_id, "datasets": datasets,
            }
            self.store.publish(snapshot)
            return {"status": "completed", "snapshot_id": snapshot["snapshot_id"], "retrieved_at": snapshot["retrieved_at"]}
        except Exception as exc:
            return {"status": "failed", "error_type": type(exc).__name__, "error_detail": str(exc)[:500]}
        finally:
            self.store.release_refresh_lock(refresh_lock)
