import json
from pathlib import Path
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from deploy.scripts.check_release_gate import validate_release_evidence


REQUIRED = {
    "tls": "tls.txt",
    "image_build": "image.txt",
    "eicar_rejection": "eicar.txt",
    "restore_drill": "restore.txt",
    "data_provider_authorization": "provider.txt",
    "security_signoff": "security.txt",
    "privacy_financial_disclosures": "legal.txt",
}


def test_missing_or_false_evidence_blocks_release(tmp_path):
    with pytest.raises(RuntimeError, match="tls"):
        validate_release_evidence({"tls": {"approved": False}}, tmp_path)


def test_complete_existing_evidence_passes(tmp_path):
    payload = {}
    for name, filename in REQUIRED.items():
        (tmp_path / filename).write_text("approved", encoding="utf-8")
        payload[name] = {"approved": True, "evidence_file": filename}

    assert validate_release_evidence(payload, tmp_path)["status"] == "passed"


def test_evidence_path_cannot_escape_manifest_directory(tmp_path):
    payload = {name: {"approved": True, "evidence_file": filename} for name, filename in REQUIRED.items()}
    payload["tls"]["evidence_file"] = "../outside.txt"

    with pytest.raises(RuntimeError, match="inside"):
        validate_release_evidence(payload, tmp_path)


def test_expired_evidence_blocks_release(tmp_path):
    payload = {}
    for name, filename in REQUIRED.items():
        (tmp_path / filename).write_text("approved", encoding="utf-8")
        payload[name] = {"approved": True, "evidence_file": filename}
    payload["tls"]["expires_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    with pytest.raises(RuntimeError, match="expired"):
        validate_release_evidence(payload, tmp_path)
