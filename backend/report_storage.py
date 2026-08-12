"""Validated, per-user report storage backed by UserReport metadata."""

from __future__ import annotations

import base64
import binascii
import os
import shlex
import subprocess
import tempfile
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import User, UserReport
from runtime_security import is_public_mode


MAX_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".md", ".markdown", ".csv", ".xls", ".xlsx", ".ppt", ".pptx", ".png", ".jpg", ".jpeg", ".webp"}
MIME_BY_EXTENSION = {".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown", ".csv": "text/csv", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def scan_report(path: Path) -> None:
    """Run the configured malware scanner before a report becomes durable."""
    if not is_public_mode():
        return
    command = (os.environ.get("VR_REPORT_SCAN_COMMAND") or "").strip()
    if command.count("{path}") != 1:
        raise RuntimeError("VR_REPORT_SCAN_COMMAND must contain exactly one {path} placeholder")
    args = shlex.split(command, posix=os.name != "nt")
    args = [part.replace("{path}", str(path)) for part in args]
    try:
        result = subprocess.run(args, capture_output=True, timeout=30, check=False, shell=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "文件安全扫描服务不可用") from exc
    if result.returncode != 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文件安全扫描未通过")


def _root() -> Path:
    return Path(os.environ.get("VR_REPORTS_DIR") or Path.home() / ".vibe-research" / "reports")


def _decode(name: str, content_b64: str) -> tuple[str, str, bytes]:
    filename = Path((name or "").replace("\\", "/")).name.strip()
    extension = Path(filename).suffix.lower()
    if not filename or extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不支持的研报文件类型")
    raw = content_b64.split(",", 1)[1] if content_b64.startswith("data:") and "," in content_b64 else content_b64
    try:
        content = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "研报内容不是有效 base64") from exc
    if not content or len(content) > MAX_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "研报文件为空或超过 25MB")
    return filename, extension, content


def _report_row(report: UserReport) -> dict:
    return {"id": report.id, "name": report.original_name, "size": report.byte_size, "ext": Path(report.original_name).suffix.lower(), "ts": int(report.created_at.timestamp() * 1000), "mime_type": report.mime_type, "industry": "未分类"}


def list_reports(db: Session, user: User) -> list[dict]:
    reports = db.execute(select(UserReport).where(UserReport.user_id == user.id).order_by(UserReport.created_at.desc())).scalars()
    return [_report_row(report) for report in reports]


def save_report(db: Session, user: User, name: str, content_b64: str) -> dict:
    filename, extension, content = _decode(name, content_b64)
    report = UserReport(user_id=user.id, original_name=filename, storage_key="", mime_type=MIME_BY_EXTENSION.get(extension, "application/octet-stream"), byte_size=len(content))
    db.add(report)
    db.flush()
    folder = _root() / user.id
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{report.id}{extension}"
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=folder, prefix=f".{report.id}-", delete=False) as handle:
            temporary_path = Path(handle.name)
            handle.write(content)
        scan_report(temporary_path)
        os.replace(temporary_path, target)
        report.storage_key = str(target)
        db.commit()
        db.refresh(report)
        return _report_row(report)
    except Exception:
        db.rollback()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise


def owned_report(db: Session, user: User, report_id: str) -> UserReport:
    report = db.execute(select(UserReport).where(UserReport.id == report_id, UserReport.user_id == user.id)).scalar_one_or_none()
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "研报不存在")
    return report


def delete_report(db: Session, user: User, report_id: str) -> None:
    report = owned_report(db, user, report_id)
    path = Path(report.storage_key)
    db.delete(report)
    db.commit()
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
