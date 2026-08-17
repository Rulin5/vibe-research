"""Atomic persistent snapshots for public dashboard data."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any


REQUIRED_DATASETS = (
    "indices", "global_indices", "market_overview", "market_emotion",
    "turnover_top", "index_candles",
)
REQUIRED_INDEX_SYMBOLS = {
    "CN.SH.000001", "CN.SZ.399001", "CN.SZ.399006", "CN.SH.000300",
    "GLOBAL.DJI", "GLOBAL.SPX", "GLOBAL.IXIC", "GLOBAL.HSI", "GLOBAL.HKTECH",
}


class PublicDataSnapshotStore:
    def __init__(self, root: str | Path):
        self.root = Path(root) / "public-data-snapshots"
        self._lock = threading.RLock()

    def _path(self, name: str) -> Path:
        return self.root / name

    def _write_json(self, path: Path, payload: Any) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)

    @staticmethod
    def _read_json(path: Path) -> dict | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    @staticmethod
    def _validate(snapshot: dict) -> None:
        if not snapshot.get("snapshot_id") or snapshot.get("status") != "completed":
            raise ValueError("snapshot must be completed and have an id")
        datasets = snapshot.get("datasets")
        if not isinstance(datasets, dict):
            raise ValueError("datasets are missing")
        for name in REQUIRED_DATASETS:
            value = datasets.get(name)
            if not value:
                raise ValueError(f"required dataset is empty: {name}")
        overview = datasets["market_overview"]
        if not isinstance(overview, dict) or not overview.get("sentiment"):
            raise ValueError("required dataset is empty: market_overview.sentiment")
        if not overview.get("sectors"):
            raise ValueError("required dataset is empty: market_overview.sectors")
        turnover = datasets["turnover_top"]
        if not isinstance(turnover, dict) or not turnover.get("stocks"):
            raise ValueError("required dataset is empty: turnover_top.stocks")
        for row in datasets["index_candles"]:
            if not isinstance(row, dict) or not row.get("symbol") or not row.get("candles"):
                raise ValueError("required dataset is empty: index_candles.candles")
        candle_symbols = {row["symbol"] for row in datasets["index_candles"]}
        if candle_symbols != REQUIRED_INDEX_SYMBOLS:
            raise ValueError("required dataset is incomplete: index_candles.symbols")
        if len(datasets["indices"]) < 4:
            raise ValueError("required dataset is incomplete: indices")
        if len(datasets["global_indices"]) < 5:
            raise ValueError("required dataset is incomplete: global_indices")

    def publish(self, snapshot: dict) -> None:
        self._validate(snapshot)
        snapshot_id = str(snapshot["snapshot_id"])
        with self._lock:
            self._write_json(self._path(f"{snapshot_id}.json"), snapshot)
            self._write_json(self._path("current.json"), {"snapshot_id": snapshot_id})

    def load_current(self) -> dict | None:
        with self._lock:
            pointer = self._read_json(self._path("current.json")) or {}
            snapshot_id = str(pointer.get("snapshot_id") or "")
            snapshot = self._read_json(self._path(f"{snapshot_id}.json")) if snapshot_id else None
            try:
                if snapshot is not None:
                    self._validate(snapshot)
            except ValueError:
                return None
            return snapshot

    def try_acquire_refresh_lock(self, stale_after_seconds: int = 1800) -> Path | None:
        lock_path = self._path("refresh.lock")
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            try:
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    if time.time() - lock_path.stat().st_mtime <= stale_after_seconds:
                        return None
                    lock_path.unlink()
                    descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                except (FileExistsError, OSError):
                    return None
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(str(os.getpid()))
                handle.flush()
                os.fsync(handle.fileno())
            return lock_path

    def release_refresh_lock(self, lock_path: Path) -> None:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
