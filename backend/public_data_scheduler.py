"""Periodic public-dashboard refresh worker."""

import logging
import os
import time

from public_data_refresh import PublicDataRefreshService


LOGGER = logging.getLogger("vibe_research.public_data_scheduler")


def main() -> int:
    interval = max(60, int(os.environ.get("VR_PUBLIC_DATA_REFRESH_INTERVAL_SECONDS", "300")))
    service = PublicDataRefreshService()
    while True:
        try:
            LOGGER.info("public_data_refresh state=%s", service.run_once("scheduled-public-data-refresh"))
        except Exception:
            LOGGER.exception("public_data_refresh_cycle_failed")
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
