import pytest

import auth
import chat
import report_storage
import runtime_security


def test_local_mode_accepts_missing_public_controls(monkeypatch):
    monkeypatch.setenv("VR_DEPLOYMENT_MODE", "local")
    monkeypatch.delenv("VR_REDIS_URL", raising=False)
    monkeypatch.delenv("VR_REPORT_SCAN_COMMAND", raising=False)

    runtime_security.enforce_startup_policy()


def test_public_mode_rejects_insecure_session_cookie(monkeypatch):
    monkeypatch.setenv("VR_DEPLOYMENT_MODE", "public")
    monkeypatch.delenv("VR_COOKIE_SECURE", raising=False)

    with pytest.raises(RuntimeError, match="VR_COOKIE_SECURE"):
        auth.cookie_secure()


def test_public_startup_requires_database_and_teajoin_configuration(monkeypatch):
    monkeypatch.setenv("VR_DEPLOYMENT_MODE", "public")
    monkeypatch.setenv("VR_COOKIE_SECURE", "true")
    monkeypatch.setenv("VR_DATABASE_URL", "postgresql+psycopg://user:password@postgres:5432/vibe_research")
    monkeypatch.setenv("TEAJOIN_API_KEY", "configured")
    monkeypatch.setenv("VR_ALLOW_ORIGINS", "https://research.example.com")
    monkeypatch.setenv("VR_REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("VR_AI_ALLOWED_HOSTS", "api.stepfun.com")
    monkeypatch.setenv("VR_REPORT_SCAN_COMMAND", "scanner {path}")
    monkeypatch.setenv("VR_CREDENTIAL_ENCRYPTION_KEY", "configured-for-startup-policy-test")
    monkeypatch.delenv("VR_DATABASE_URL", raising=False)
    monkeypatch.setenv("TEAJOIN_API_KEY", "configured")

    with pytest.raises(RuntimeError, match="VR_DATABASE_URL"):
        runtime_security.enforce_startup_policy()


@pytest.mark.parametrize(
    "missing, message",
    [
        ("VR_REDIS_URL", "VR_REDIS_URL"),
        ("VR_AI_ALLOWED_HOSTS", "VR_AI_ALLOWED_HOSTS"),
        ("VR_REPORT_SCAN_COMMAND", "VR_REPORT_SCAN_COMMAND"),
        ("VR_CREDENTIAL_ENCRYPTION_KEY", "VR_CREDENTIAL_ENCRYPTION_KEY"),
    ],
)
def test_public_startup_rejects_missing_required_control(monkeypatch, missing, message):
    monkeypatch.setenv("VR_DEPLOYMENT_MODE", "public")
    monkeypatch.setenv("VR_COOKIE_SECURE", "true")
    monkeypatch.setenv("VR_ALLOW_ORIGINS", "https://research.example.com")
    monkeypatch.setenv("VR_REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("VR_AI_ALLOWED_HOSTS", "api.stepfun.com")
    monkeypatch.setenv("VR_REPORT_SCAN_COMMAND", "scanner {path}")
    monkeypatch.setenv("VR_CREDENTIAL_ENCRYPTION_KEY", "configured-for-startup-policy-test")
    monkeypatch.setenv("VR_DATABASE_URL", "postgresql+psycopg://user:password@postgres:5432/vibe_research")
    monkeypatch.setenv("TEAJOIN_API_KEY", "configured")
    monkeypatch.delenv(missing)

    with pytest.raises(RuntimeError, match=message):
        runtime_security.enforce_startup_policy()


def test_public_mode_rejects_loopback_custom_ai_endpoint(monkeypatch):
    monkeypatch.setenv("VR_DEPLOYMENT_MODE", "public")
    monkeypatch.setenv("VR_AI_ALLOWED_HOSTS", "api.stepfun.com")

    with pytest.raises(RuntimeError, match="Base URL"):
        chat._check_base_url("http://127.0.0.1:11434/v1")


def test_public_mode_rejects_report_when_scanner_fails(tmp_path, monkeypatch):
    report = tmp_path / "research.pdf"
    report.write_bytes(b"not-a-real-pdf")
    monkeypatch.setenv("VR_DEPLOYMENT_MODE", "public")
    monkeypatch.setenv("VR_REPORT_SCAN_COMMAND", "scanner {path}")

    class FailedScan:
        returncode = 1

    monkeypatch.setattr(report_storage.subprocess, "run", lambda *args, **kwargs: FailedScan())

    with pytest.raises(Exception, match="安全扫描"):
        report_storage.scan_report(report)


def test_public_mode_scanner_receives_file_without_shell(tmp_path, monkeypatch):
    report = tmp_path / "research report.pdf"
    report.write_bytes(b"not-a-real-pdf")
    monkeypatch.setenv("VR_DEPLOYMENT_MODE", "public")
    monkeypatch.setenv("VR_REPORT_SCAN_COMMAND", "scanner --file {path}")
    observed = {}

    class SuccessfulScan:
        returncode = 0

    def fake_run(args, **kwargs):
        observed["args"] = args
        observed["kwargs"] = kwargs
        return SuccessfulScan()

    monkeypatch.setattr(report_storage.subprocess, "run", fake_run)
    report_storage.scan_report(report)

    assert observed["args"][-1] == str(report)
    assert observed["kwargs"]["shell"] is False
