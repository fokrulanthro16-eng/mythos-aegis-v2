"""Tests for app/secrets/rotation.py — rotation service and multi-key verification."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import jwt
import pytest

from app.auth.jwt import (
    TokenExpiredError,
    TokenInvalidError,
    validate_token,
)
from app.core.config import settings
from app.secrets.rotation import KeyRotationService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALL_PERMS = ["orders.cancel", "analytics.read", "policies.read", "vision.analyze"]

_KEY_A = "key-alpha-used-for-signing-before-rotation-32c"
_KEY_B = "key-beta-used-for-signing-after-rotation--32c"


def _make_token(
    *,
    secret: str | None = None,
    expired: bool = False,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": str(uuid4()),
        "tenant_id": str(uuid4()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": now,
        "exp": now - timedelta(seconds=1) if expired else now + timedelta(hours=1),
        "roles": ["user"],
        "permissions": _ALL_PERMS,
    }
    key = secret if secret is not None else settings.JWT_SECRET
    return jwt.encode(payload, key, algorithm=settings.JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# KeyRotationService — initial state
# ---------------------------------------------------------------------------


def test_rotation_service_stores_current_key() -> None:
    svc = KeyRotationService(current_key=_KEY_A)
    assert svc.get_current_key() == _KEY_A


def test_rotation_service_no_previous_key_by_default() -> None:
    svc = KeyRotationService(current_key=_KEY_A)
    assert svc.get_previous_key() is None


def test_rotation_service_stores_optional_previous_key() -> None:
    svc = KeyRotationService(current_key=_KEY_B, previous_key=_KEY_A)
    assert svc.get_previous_key() == _KEY_A


def test_rotation_service_rejects_empty_current_key() -> None:
    with pytest.raises(ValueError, match="current_key"):
        KeyRotationService(current_key="")


def test_get_keypair_masks_values() -> None:
    svc = KeyRotationService(current_key=_KEY_A, previous_key=_KEY_B)
    kp = svc.get_keypair()
    rep = repr(kp)
    assert _KEY_A not in rep
    assert _KEY_B not in rep


# ---------------------------------------------------------------------------
# KeyRotationService — promote_new_key
# ---------------------------------------------------------------------------


def test_promote_new_key_updates_current() -> None:
    svc = KeyRotationService(current_key=_KEY_A)
    svc.promote_new_key(_KEY_B)
    assert svc.get_current_key() == _KEY_B


def test_promote_new_key_preserves_old_as_previous() -> None:
    svc = KeyRotationService(current_key=_KEY_A)
    svc.promote_new_key(_KEY_B)
    assert svc.get_previous_key() == _KEY_A


def test_promote_new_key_overwrites_existing_previous() -> None:
    """Second rotation: current→previous replaces the last previous."""
    svc = KeyRotationService(current_key=_KEY_A)
    svc.promote_new_key(_KEY_B)
    key_c = "key-gamma-third-signing-key-value-32c"
    svc.promote_new_key(key_c)
    assert svc.get_current_key() == key_c
    assert svc.get_previous_key() == _KEY_B  # _KEY_A is gone


def test_promote_new_key_rejects_empty_key() -> None:
    svc = KeyRotationService(current_key=_KEY_A)
    with pytest.raises(ValueError, match="new_key"):
        svc.promote_new_key("")


# ---------------------------------------------------------------------------
# KeyRotationService — retire_old_key
# ---------------------------------------------------------------------------


def test_retire_old_key_clears_previous() -> None:
    svc = KeyRotationService(current_key=_KEY_A)
    svc.promote_new_key(_KEY_B)
    assert svc.get_previous_key() is not None
    svc.retire_old_key()
    assert svc.get_previous_key() is None


def test_retire_old_key_noop_when_no_previous() -> None:
    svc = KeyRotationService(current_key=_KEY_A)
    svc.retire_old_key()  # must not raise
    assert svc.get_current_key() == _KEY_A


def test_retire_old_key_does_not_affect_current() -> None:
    svc = KeyRotationService(current_key=_KEY_A)
    svc.promote_new_key(_KEY_B)
    svc.retire_old_key()
    assert svc.get_current_key() == _KEY_B


# ---------------------------------------------------------------------------
# Audit logging — event tags present, key values never logged
# ---------------------------------------------------------------------------


def test_promote_logs_rotation_event(caplog: pytest.LogCaptureFixture) -> None:
    svc = KeyRotationService(current_key=_KEY_A)
    with caplog.at_level(logging.INFO, logger="app.secrets.rotation"):
        svc.promote_new_key(_KEY_B)
    messages = [r.getMessage() for r in caplog.records]
    assert any("promoted" in m.lower() or "rotation" in m.lower() for m in messages)


def test_promote_never_logs_key_value(caplog: pytest.LogCaptureFixture) -> None:
    svc = KeyRotationService(current_key=_KEY_A)
    with caplog.at_level(logging.DEBUG, logger="app.secrets.rotation"):
        svc.promote_new_key(_KEY_B)
    for record in caplog.records:
        assert _KEY_A not in record.getMessage()
        assert _KEY_B not in record.getMessage()


def test_retire_logs_retirement_event(caplog: pytest.LogCaptureFixture) -> None:
    svc = KeyRotationService(current_key=_KEY_A, previous_key=_KEY_B)
    with caplog.at_level(logging.INFO, logger="app.secrets.rotation"):
        svc.retire_old_key()
    messages = [r.getMessage() for r in caplog.records]
    assert any("retire" in m.lower() for m in messages)


def test_retire_never_logs_key_value(caplog: pytest.LogCaptureFixture) -> None:
    svc = KeyRotationService(current_key=_KEY_A, previous_key=_KEY_B)
    with caplog.at_level(logging.DEBUG, logger="app.secrets.rotation"):
        svc.retire_old_key()
    for record in caplog.records:
        assert _KEY_B not in record.getMessage()


# ---------------------------------------------------------------------------
# Rotation metrics
# ---------------------------------------------------------------------------


def test_promote_increments_rotation_metric() -> None:
    svc = KeyRotationService(current_key=_KEY_A)
    with patch("app.secrets.rotation.secret_rotation_total") as mock_counter:
        svc.promote_new_key(_KEY_B)
    mock_counter.labels.assert_called_with(event="promoted")
    mock_counter.labels.return_value.inc.assert_called()


def test_retire_increments_rotation_metric() -> None:
    svc = KeyRotationService(current_key=_KEY_A, previous_key=_KEY_B)
    with patch("app.secrets.rotation.secret_rotation_total") as mock_counter:
        svc.retire_old_key()
    mock_counter.labels.assert_called_with(event="retired")
    mock_counter.labels.return_value.inc.assert_called()


def test_retire_noop_does_not_increment_metric() -> None:
    svc = KeyRotationService(current_key=_KEY_A)  # no previous key
    with patch("app.secrets.rotation.secret_rotation_total") as mock_counter:
        svc.retire_old_key()
    mock_counter.labels.return_value.inc.assert_not_called()


# ---------------------------------------------------------------------------
# JWT multi-key verification
# ---------------------------------------------------------------------------


def test_current_key_signs_and_verifies() -> None:
    """Baseline: token signed with current key passes validation."""
    svc = KeyRotationService(current_key=_KEY_A)
    token = _make_token(secret=_KEY_A)
    claims = validate_token(token, rotation_service=svc)
    assert claims is not None


def test_previous_key_still_verifies_after_rotation() -> None:
    """Tokens signed before rotation remain valid during the overlap window."""
    svc = KeyRotationService(current_key=_KEY_A)
    # Token issued with key A (the current key before rotation)
    token = _make_token(secret=_KEY_A)
    # Rotate to key B — key A becomes previous
    svc.promote_new_key(_KEY_B)
    # Token signed with key A must still be accepted
    claims = validate_token(token, rotation_service=svc)
    assert claims is not None


def test_new_current_key_verifies_after_rotation() -> None:
    """After rotation, tokens signed with the new key are accepted."""
    svc = KeyRotationService(current_key=_KEY_A)
    svc.promote_new_key(_KEY_B)
    token = _make_token(secret=_KEY_B)
    claims = validate_token(token, rotation_service=svc)
    assert claims is not None


def test_retired_key_is_rejected() -> None:
    """After retire_old_key(), tokens signed with the old key are invalid."""
    svc = KeyRotationService(current_key=_KEY_A)
    token_with_old_key = _make_token(secret=_KEY_A)
    svc.promote_new_key(_KEY_B)
    # Key A is accepted now (as previous)
    validate_token(token_with_old_key, rotation_service=svc)  # passes
    svc.retire_old_key()
    # Key A is no longer accepted
    with pytest.raises(TokenInvalidError):
        validate_token(token_with_old_key, rotation_service=svc)


def test_unknown_key_always_rejected() -> None:
    """A token signed with a completely unknown key is always rejected."""
    svc = KeyRotationService(current_key=_KEY_A)
    unknown_key = "completely-unknown-key-never-in-service-x"
    token = _make_token(secret=unknown_key)
    with pytest.raises(TokenInvalidError):
        validate_token(token, rotation_service=svc)


def test_expired_token_rejected_even_with_correct_key() -> None:
    """Expiry check happens before key fallback — expired tokens always fail."""
    svc = KeyRotationService(current_key=_KEY_A)
    token = _make_token(secret=_KEY_A, expired=True)
    with pytest.raises(TokenExpiredError):
        validate_token(token, rotation_service=svc)


def test_expired_token_not_retried_with_previous_key() -> None:
    """Expiry is not key-specific — should not retry with previous key."""
    svc = KeyRotationService(current_key=_KEY_B, previous_key=_KEY_A)
    # Token signed with current key but expired — don't retry with previous
    token = _make_token(secret=_KEY_B, expired=True)
    with pytest.raises(TokenExpiredError):
        validate_token(token, rotation_service=svc)


def test_wrong_issuer_rejected_without_key_retry() -> None:
    """Issuer mismatch is not key-specific — should NOT retry."""
    svc = KeyRotationService(current_key=_KEY_A, previous_key=_KEY_B)
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": str(uuid4()),
        "tenant_id": str(uuid4()),
        "iss": "wrong-issuer",
        "aud": settings.JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(hours=1),
        "roles": ["user"],
        "permissions": _ALL_PERMS,
    }
    token = jwt.encode(payload, _KEY_A, algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(TokenInvalidError):
        validate_token(token, rotation_service=svc)


# ---------------------------------------------------------------------------
# Production weak-key rejection (via SecretManager.validate_secret)
# ---------------------------------------------------------------------------


def test_weak_production_secret_rejected_by_manager() -> None:
    from app.secrets.manager import SecretManager

    manager = SecretManager()
    with pytest.raises(ValueError):
        manager.validate_secret("JWT_SECRET", "weak", env="production")


def test_short_32_char_boundary() -> None:
    from app.secrets.manager import _MIN_KEY_LEN, SecretManager

    manager = SecretManager()
    boundary = "x" * _MIN_KEY_LEN
    manager.validate_secret("JWT_SECRET", boundary, env="production")  # passes


def test_31_char_key_rejected_in_production() -> None:
    from app.secrets.manager import _MIN_KEY_LEN, SecretManager

    manager = SecretManager()
    with pytest.raises(ValueError, match=f"≥{_MIN_KEY_LEN}"):
        manager.validate_secret(
            "JWT_SECRET", "x" * (_MIN_KEY_LEN - 1), env="production"
        )


# ---------------------------------------------------------------------------
# End-to-end: default rotation service uses settings.JWT_SECRET
# ---------------------------------------------------------------------------


def test_default_service_uses_settings_jwt_secret() -> None:
    """validate_token without explicit service uses the process-wide singleton."""
    token = _make_token()  # encoded with settings.JWT_SECRET
    # If this raises, the singleton is not initialised from settings
    claims = validate_token(token)
    assert claims is not None
