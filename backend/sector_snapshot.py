"""经校验的板块快照持久化：公开读路径只读取完整发布的同一版本。"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any


class SectorSnapshotStore:
    def __init__(self, root: str | Path):
        self.root = Path(root) / "sector-snapshots"
        self._lock = threading.RLock()

    def _path(self, name: str) -> Path:
        return self.root / name

    def _write_json(self, path: Path, payload: Any) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)

    @staticmethod
    def _read_json(path: Path) -> dict | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def save_refresh_state(self, state: dict) -> None:
        with self._lock:
            self._write_json(self._path("refresh-state.json"), state)

    def load_refresh_state(self) -> dict | None:
        with self._lock:
            return self._read_json(self._path("refresh-state.json"))

    def publish(self, snapshot: dict, members: dict[tuple[str, str], list[dict]] | None = None) -> None:
        snapshot_id = str(snapshot.get("snapshot_id") or "").strip()
        if not snapshot_id or snapshot.get("status") != "completed":
            raise ValueError("only completed snapshots with an id can be published")
        serialized_members = {f"{kind}|{code}": rows for (kind, code), rows in (members or {}).items()}
        with self._lock:
            self._write_json(self._path(f"{snapshot_id}-members.json"), serialized_members)
            self._write_json(self._path(f"{snapshot_id}.json"), snapshot)
            self._write_json(self._path("current.json"), {"snapshot_id": snapshot_id})

    def load_snapshot(self, snapshot_id: str) -> dict | None:
        with self._lock:
            snapshot = self._read_json(self._path(f"{snapshot_id}.json"))
            return snapshot if snapshot and snapshot.get("status") == "completed" else None

    def load_current(self) -> dict | None:
        with self._lock:
            pointer = self._read_json(self._path("current.json"))
            snapshot_id = str((pointer or {}).get("snapshot_id") or "")
            return self.load_snapshot(snapshot_id) if snapshot_id else None

    def load_members(self, snapshot_id: str, kind: str, code: str) -> list[dict]:
        with self._lock:
            payload = self._read_json(self._path(f"{snapshot_id}-members.json")) or {}
            rows = payload.get(f"{kind}|{code}")
            return rows if isinstance(rows, list) else []
