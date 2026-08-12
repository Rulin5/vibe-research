"""Per-user AI credentials with server-side encryption and a fixed provider contract."""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from chat import _check_base_url
from models import User, UserAiCredential


PROVIDER = "stepfun"
MODEL = "step-3.7-flash"
BASE_URL = "https://api.stepfun.com/step_plan/v1"


def _cipher_for_material(material: str) -> Fernet:
    if not material:
        raise RuntimeError("VR_CREDENTIAL_ENCRYPTION_KEY is required for AI credential storage")
    key = base64.urlsafe_b64encode(hashlib.sha256(material.encode("utf-8")).digest())
    return Fernet(key)


def _current_cipher() -> Fernet:
    return _cipher_for_material(os.environ.get("VR_CREDENTIAL_ENCRYPTION_KEY", ""))


def _previous_cipher() -> Fernet | None:
    material = (os.environ.get("VR_CREDENTIAL_ENCRYPTION_KEY_PREVIOUS") or "").strip()
    return _cipher_for_material(material) if material else None


def _cipher() -> Fernet:
    """Compatibility alias for existing callers and tests."""
    return _current_cipher()


def decrypt_secret(db: Session, credential: UserAiCredential) -> tuple[str, bool]:
    encoded = credential.encrypted_secret.encode("ascii")
    try:
        return _current_cipher().decrypt(encoded).decode("utf-8"), False
    except InvalidToken:
        previous = _previous_cipher()
        if previous is None:
            raise
        plaintext = previous.decrypt(encoded)
        credential.encrypted_secret = _current_cipher().encrypt(plaintext).decode("ascii")
        db.commit()
        return plaintext.decode("utf-8"), True


def rotate_all_credentials(db: Session) -> dict[str, int]:
    rows = db.execute(select(UserAiCredential)).scalars().all()
    pending: list[tuple[UserAiCredential, str]] = []
    current = 0
    failed = 0
    for credential in rows:
        encoded = credential.encrypted_secret.encode("ascii")
        try:
            _current_cipher().decrypt(encoded)
            current += 1
            continue
        except (InvalidToken, UnicodeError):
            pass
        previous = _previous_cipher()
        if previous is None:
            failed += 1
            continue
        try:
            plaintext = previous.decrypt(encoded)
            pending.append((credential, _current_cipher().encrypt(plaintext).decode("ascii")))
        except (InvalidToken, UnicodeError):
            failed += 1
    if failed:
        db.rollback()
        return {"total": len(rows), "rotated": 0, "current": 0, "failed": failed}
    for credential, encrypted in pending:
        credential.encrypted_secret = encrypted
    db.commit()
    return {"total": len(rows), "rotated": len(pending), "current": current, "failed": 0}


def status_payload(db: Session, user: User) -> dict:
    credential = db.execute(
        select(UserAiCredential).where(UserAiCredential.user_id == user.id, UserAiCredential.provider == PROVIDER)
    ).scalar_one_or_none()
    return {
        "configured": credential is not None,
        "active_source": "user" if credential is not None else ("system" if _system_key() else "none"),
        "provider": PROVIDER,
        "base_url": credential.base_url if credential and credential.base_url else _system_base_url(),
        "model": credential.model_id if credential and credential.model_id else _system_model(),
        "key_suffix": credential.key_suffix if credential else None,
    }


def _system_key() -> str:
    return (os.environ.get("VR_AI_STEPFUN_API_KEY") or "").strip()


def _system_model() -> str:
    return (os.environ.get("VR_AI_STEPFUN_MODEL") or MODEL).strip()


def _system_base_url() -> str:
    return (os.environ.get("VR_AI_STEPFUN_BASE_URL") or BASE_URL).strip()


def save_credential(db: Session, user: User, api_key: str, base_url: str, model: str) -> dict:
    secret = (api_key or "").strip()
    normalized_base_url = (base_url or "").strip()
    normalized_model = (model or "").strip()
    if len(secret) < 1 or len(secret) > 2048:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "AI key length is invalid")
    if not normalized_base_url or not normalized_model or len(normalized_base_url) > 2048 or len(normalized_model) > 256:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "AI endpoint and model are required")
    try:
        _check_base_url(normalized_base_url)
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    credential = db.execute(
        select(UserAiCredential).where(UserAiCredential.user_id == user.id, UserAiCredential.provider == PROVIDER)
    ).scalar_one_or_none()
    encrypted = _current_cipher().encrypt(secret.encode("utf-8")).decode("ascii")
    if credential is None:
        credential = UserAiCredential(
            user_id=user.id,
            provider=PROVIDER,
            encrypted_secret=encrypted,
            key_suffix=secret[-4:],
            base_url=normalized_base_url,
            model_id=normalized_model,
        )
        db.add(credential)
    else:
        credential.encrypted_secret = encrypted
        credential.key_suffix = secret[-4:]
        credential.base_url = normalized_base_url
        credential.model_id = normalized_model
    db.commit()
    return status_payload(db, user)


def delete_credential(db: Session, user: User) -> None:
    credential = db.execute(
        select(UserAiCredential).where(UserAiCredential.user_id == user.id, UserAiCredential.provider == PROVIDER)
    ).scalar_one_or_none()
    if credential is not None:
        db.delete(credential)
        db.commit()


def runtime_config(db: Session, user: User) -> dict:
    credential = db.execute(
        select(UserAiCredential).where(UserAiCredential.user_id == user.id, UserAiCredential.provider == PROVIDER)
    ).scalar_one_or_none()
    if credential is None:
        system_key = _system_key()
        if not system_key:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "AI credential is not configured")
        return {"provider": PROVIDER, "baseURL": _system_base_url(), "apiKey": system_key, "model": _system_model()}
    try:
        secret, _ = decrypt_secret(db, credential)
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Stored AI credential cannot be decrypted") from exc
    return {"provider": PROVIDER, "baseURL": credential.base_url or _system_base_url(), "apiKey": secret, "model": credential.model_id or _system_model()}
