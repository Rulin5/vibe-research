"""经校验的板块快照持久化：公开读路径只读取完整发布的同一版本。"""
from __future__ import annotations

import json
import os
import threading
import time
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

    def try_acquire_refresh_lock(self, stale_after_seconds: int = 1800) -> Path | None:
        """Acquire a filesystem lock shared by API and scheduler containers."""
        lock_path = self._path("refresh.lock")
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            try:
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    age_seconds = time.time() - lock_path.stat().st_mtime
                    owner_text = lock_path.read_text(encoding="utf-8").strip()
                    owner_pid = int(owner_text)
                    try:
                        os.kill(owner_pid, 0)
                        owner_is_dead = False
                    except ProcessLookupError:
                        owner_is_dead = True
                    except PermissionError:
                        owner_is_dead = False
                    is_stale = age_seconds > stale_after_seconds or owner_is_dead
                except OSError:
                    return None
                except ValueError:
                    is_stale = True
                if not is_stale:
                    return None
                try:
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
        with self._lock:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

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

    def load_all_members(self, snapshot_id: str) -> dict[tuple[str, str], list[dict]]:
        """Load a verified member map for same-trade-date refresh reuse."""
        with self._lock:
            payload = self._read_json(self._path(f"{snapshot_id}-members.json")) or {}
        result: dict[tuple[str, str], list[dict]] = {}
        for compound_key, rows in payload.items():
            kind, separator, code = str(compound_key).partition("|")
            if separator and kind and code and isinstance(rows, list) and rows:
                result[(kind, code)] = rows
        return result
