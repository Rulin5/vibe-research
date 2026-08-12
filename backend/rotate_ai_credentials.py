"""Bulk re-encrypt user AI credentials with the configured current key."""

from __future__ import annotations

import json

from ai_credentials import rotate_all_credentials
from db import session_factory


def main() -> int:
    with session_factory()() as db:
        summary = rotate_all_credentials(db)
    print(json.dumps(summary, separators=(",", ":")))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
