"""Password storage, and the migration off PBKDF2.

Argon2id is the default for everything new. The point of interest is what
happens to accounts created before it: they must keep working, and they must
end up on Argon2id without anyone being emailed a reset link.
"""

import base64
import hashlib
import secrets

import pytest

from app.auth.security import (
    hash_password,
    needs_rehash,
    unusable_password_hash,
    verify_password,
)

PASSWORD = "C0rrect-Horse!"


def legacy_pbkdf2_hash(password: str, iterations: int = 260_000) -> str:
    """A hash in exactly the format Triplet wrote before this change."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return (
        f"pbkdf2_sha256${iterations}$"
        f"{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"
    )


def test_new_passwords_use_argon2id():
    assert hash_password(PASSWORD).startswith("$argon2id$")


def test_a_correct_password_verifies():
    assert verify_password(PASSWORD, hash_password(PASSWORD))


def test_a_wrong_password_is_rejected():
    assert not verify_password("something-else", hash_password(PASSWORD))


def test_the_same_password_hashes_differently_each_time():
    """Salting, checked rather than assumed."""
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


def test_a_legacy_pbkdf2_password_still_verifies():
    """Existing users must not be locked out by the change."""
    assert verify_password(PASSWORD, legacy_pbkdf2_hash(PASSWORD))


def test_a_wrong_password_against_a_legacy_hash_is_rejected():
    assert not verify_password("something-else", legacy_pbkdf2_hash(PASSWORD))


def test_a_legacy_hash_is_flagged_for_upgrade():
    assert needs_rehash(legacy_pbkdf2_hash(PASSWORD)) is True


def test_a_current_argon2_hash_is_not_re_upgraded():
    assert needs_rehash(hash_password(PASSWORD)) is False


def test_an_oauth_account_has_no_password_to_verify():
    """An unusable-password marker must never satisfy a login."""
    marker = unusable_password_hash()

    assert verify_password("", marker) is False
    assert verify_password(marker, marker) is False
    assert needs_rehash(marker) is False


def test_a_malformed_hash_is_rejected_rather_than_raising():
    assert verify_password(PASSWORD, "not-a-hash") is False
    assert verify_password(PASSWORD, "") is False
    assert verify_password(PASSWORD, None) is False


def test_login_transparently_rehashes_a_legacy_password(db_session):
    """The migration: log in once with an old hash, and it is replaced."""
    from app.auth.service import AuthService
    from app.db.models import UserDB
    from uuid import uuid4

    user = UserDB(
        id=str(uuid4()),
        email="legacy@example.com",
        password_hash=legacy_pbkdf2_hash(PASSWORD),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    assert user.password_hash.startswith("pbkdf2_sha256$")

    AuthService(db_session).login("legacy@example.com", PASSWORD)

    db_session.refresh(user)
    assert user.password_hash.startswith("$argon2id$")
    # And the account still works on the next login, now via Argon2.
    assert verify_password(PASSWORD, user.password_hash)


def test_a_failed_login_does_not_rehash(db_session):
    from app.auth.service import AuthError, AuthService
    from app.db.models import UserDB
    from uuid import uuid4

    original = legacy_pbkdf2_hash(PASSWORD)
    user = UserDB(
        id=str(uuid4()), email="legacy2@example.com", password_hash=original, is_active=True
    )
    db_session.add(user)
    db_session.commit()

    with pytest.raises(AuthError):
        AuthService(db_session).login("legacy2@example.com", "wrong-password")

    db_session.refresh(user)
    assert user.password_hash == original
