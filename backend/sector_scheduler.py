"""Dedicated periodic sector-refresh worker, isolated from the HTTP API."""

from __future__ import annotations

import logging
import os
import time

from sector_refresh import SectorRefreshService


LOGGER = logging.getLogger("vibe_research.sector_scheduler")
DEFAULT_INTERVAL_SECONDS = 300


def refresh_if_needed() -> dict:
    service = SectorRefreshService()
    # The loop interval is the freshness boundary. Same-day constituents are
    # reused by SectorRefreshService, while dated summary rows are refreshed.
    return service.run_once("scheduled-sector-refresh")


def main() -> int:
    interval = max(60, int(os.environ.get("VR_SECTOR_REFRESH_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)))
    while True:
        try:
            state = refresh_if_needed()
            LOGGER.info("sector_scheduler_cycle state=%s", state)
        except Exception:
            LOGGER.exception("sector_scheduler_cycle_failed")
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
