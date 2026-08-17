"""Fail-closed validator for external release evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


REQUIRED = (
    "tls",
    "image_build",
    "eicar_rejection",
    "restore_drill",
    "data_provider_authorization",
    "security_signoff",
    "privacy_financial_disclosures",
)


def validate_release_evidence(payload: dict, base_dir: Path) -> dict[str, object]:
    root = base_dir.resolve()
    for name in REQUIRED:
        item = payload.get(name) or {}
        if item.get("approved") is not True:
            raise RuntimeError(f"release evidence is not approved: {name}")
        approver = item.get("approved_by")
        if not isinstance(approver, str) or not approver.strip():
            raise RuntimeError(f"release evidence approver is missing: {name}")
        approved_at = item.get("approved_at")
        try:
            approved_time = datetime.fromisoformat(str(approved_at).replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"release evidence approval timestamp is invalid: {name}") from exc
        if approved_time.tzinfo is None or approved_time > datetime.now(timezone.utc):
            raise RuntimeError(f"release evidence approval timestamp is invalid: {name}")
        relative = item.get("evidence_file")
        if not isinstance(relative, str) or not relative:
            raise RuntimeError(f"release evidence file is missing: {name}")
        expires_at = item.get("expires_at")
        if expires_at:
            try:
                expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            except (TypeError, ValueError) as exc:
                raise RuntimeError(f"release evidence expiry is invalid: {name}") from exc
            if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
                raise RuntimeError(f"release evidence is expired: {name}")
        evidence = (root / relative).resolve()
        if root not in evidence.parents:
            raise RuntimeError(f"evidence files must stay inside the manifest directory: {name}")
        if not evidence.is_file():
            raise RuntimeError(f"release evidence file does not exist: {name}")
    return {"status": "passed", "checked": len(REQUIRED)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    manifest = args.evidence.resolve()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    try:
        result = validate_release_evidence(payload, manifest.parent)
    except RuntimeError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
