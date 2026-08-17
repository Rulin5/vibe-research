"""One-shot deployment gate for the durable verified sector snapshot."""

from __future__ import annotations

import logging

from sector_refresh import SectorRefreshService


LOGGER = logging.getLogger("vibe_research.sector_bootstrap")


def ensure_ready(request_id: str) -> None:
    service = SectorRefreshService()
    before = service.readiness()
    if before["ok"]:
        LOGGER.info("sector_snapshot_ready snapshot_id=%s", before.get("snapshot_id"))
        return
    state = service.run_once(request_id)
    after = service.readiness()
    if state.get("status") == "completed" and after["ok"]:
        LOGGER.info("sector_snapshot_bootstrapped snapshot_id=%s", after.get("snapshot_id"))
        return
    LOGGER.error("sector_snapshot_bootstrap_failed state=%s readiness=%s", state, after)
    raise RuntimeError(f"verified sector snapshot is not ready: {after}")


def main() -> int:
    try:
        ensure_ready("deployment-sector-bootstrap")
    except RuntimeError:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
