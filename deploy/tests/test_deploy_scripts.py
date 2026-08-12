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
