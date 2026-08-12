from types import SimpleNamespace

import pytest
from cryptography.fernet import InvalidToken

import ai_credentials


class FakeDb:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.commits = 0
        self.rollbacks = 0

    class Result:
        def __init__(self, rows):
            self.rows = rows

        def scalars(self):
            return self

        def all(self):
            return self.rows

    def execute(self, _statement):
        return self.Result(self.rows)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _row(encrypted):
    return SimpleNamespace(encrypted_secret=encrypted)


def test_previous_key_decrypts_and_lazily_reencrypts(monkeypatch):
    monkeypatch.setenv("VR_CREDENTIAL_ENCRYPTION_KEY", "new-key")
    monkeypatch.setenv("VR_CREDENTIAL_ENCRYPTION_KEY_PREVIOUS", "old-key")
    old_cipher = ai_credentials._cipher_for_material("old-key")
    row = _row(old_cipher.encrypt(b"secret-value").decode("ascii"))
    db = FakeDb()

    secret, rotated = ai_credentials.decrypt_secret(db, row)

    assert secret == "secret-value"
    assert rotated is True
    assert db.commits == 1
    assert ai_credentials._current_cipher().decrypt(row.encrypted_secret.encode("ascii")) == b"secret-value"


def test_wrong_keys_fail_without_mutating_ciphertext(monkeypatch):
    monkeypatch.setenv("VR_CREDENTIAL_ENCRYPTION_KEY", "wrong-new")
    monkeypatch.setenv("VR_CREDENTIAL_ENCRYPTION_KEY_PREVIOUS", "wrong-old")
    ciphertext = ai_credentials._cipher_for_material("actual-key").encrypt(b"secret").decode("ascii")
    row = _row(ciphertext)

    with pytest.raises(InvalidToken):
        ai_credentials.decrypt_secret(FakeDb(), row)

    assert row.encrypted_secret == ciphertext


def test_bulk_rotation_is_atomic_when_any_row_cannot_decrypt(monkeypatch):
    monkeypatch.setenv("VR_CREDENTIAL_ENCRYPTION_KEY", "new-key")
    monkeypatch.setenv("VR_CREDENTIAL_ENCRYPTION_KEY_PREVIOUS", "old-key")
    old_cipher = ai_credentials._cipher_for_material("old-key")
    valid = _row(old_cipher.encrypt(b"valid").decode("ascii"))
    invalid = _row("not-fernet")
    original = valid.encrypted_secret
    db = FakeDb([valid, invalid])

    summary = ai_credentials.rotate_all_credentials(db)

    assert summary == {"total": 2, "rotated": 0, "current": 0, "failed": 1}
    assert valid.encrypted_secret == original
    assert db.commits == 0
    assert db.rollbacks == 1
