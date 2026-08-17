from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "deploy" / "scripts"


def read(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


def test_restore_drill_is_guarded_and_records_evidence():
    source = read("restore-drill.ps1")
    assert "_restore_test" in source
    assert "EvidencePath" in source
    assert "pg_restore" in source
    assert "Resolve-Path" in source


def test_stack_verification_checks_https_headers_and_eicar():
    source = read("verify-stack.ps1")
    assert "https://" in source
    assert "Strict-Transport-Security" in source
    assert "EicarFile" in source
    assert "EvidencePath" in source


def test_backup_uses_custom_format_and_explicit_paths():
    source = read("backup.ps1")
    assert "pg_dump" in source
    assert "--format=custom" in source
    assert "BackupDirectory" in source


def test_staging_certificate_is_never_described_as_public_trust():
    source = read("new-staging-certificate.ps1")
    assert "staging" in source.lower()
    assert "public-trust" in source.lower()


def test_compose_persists_sector_snapshots_and_migrates_before_api_startup():
    root = ROOT
    for filename in ("compose.demo.yaml", "compose.production.yaml"):
        compose = (root / filename).read_text(encoding="utf-8")
        assert "sector_data:/data/runtime" in compose
        assert "VR_DATA_DIR: /data/runtime" in compose
        assert "VR_REQUIRE_FRESH_SECTOR_SNAPSHOT: \"true\"" in compose
        assert "migrate: {condition: service_completed_successfully}" in compose
        assert 'profiles: ["migration"]' not in compose
        assert "sector-bootstrap:" in compose
        assert "sector-bootstrap: {condition: service_completed_successfully}" in compose
        assert "sector-scheduler:" in compose
        assert 'VR_SECTOR_REFRESH_INTERVAL_SECONDS: "300"' in compose
from pathlib import Path


def test_preflight_script_blocks_placeholder_secrets_and_validates_compose():
    script = (Path(__file__).resolve().parents[1] / "scripts" / "preflight.ps1").read_text(encoding="utf-8")

    assert "CHANGE_ME" in script
    assert "docker compose" in script
    assert "config --quiet" in script


def test_dockerignore_excludes_deployment_secrets_from_build_context():
    dockerignore = (Path(__file__).resolve().parents[2] / ".dockerignore").read_text(encoding="utf-8")

    assert "deploy/production.env" in dockerignore


def test_public_dashboard_snapshot_is_bootstrapped_before_api_and_refreshed_outside_http():
    root = Path(__file__).resolve().parents[2]
    for name in ("compose.production.yaml", "compose.demo.yaml"):
        compose = (root / name).read_text(encoding="utf-8")
        assert "public-data-bootstrap:" in compose
        assert "public-data-scheduler:" in compose
        assert "public_data_bootstrap.py" in compose
        assert "public_data_scheduler.py" in compose
        assert "public-data-bootstrap: {condition: service_completed_successfully}" in compose
        assert "sector_data:/data/runtime" in compose
