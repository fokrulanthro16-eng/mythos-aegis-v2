"""JWT key rotation service.

Zero-downtime rotation protocol
--------------------------------
1. ``promote_new_key(new_key)``
   - ``new_key``   → becomes *current* (used for signing).
   - old *current* → becomes *previous* (still accepted for verification).
   - Outstanding tokens signed by the old key remain valid until they expire.

2. Wait at least ``JWT_EXPIRY_SECONDS`` so all old-key tokens expire.

3. ``retire_old_key()``
   - *previous* is cleared.
   - Only *current* key is accepted for verification from this point on.

Audit rules
-----------
- Every rotation event is logged at INFO with an ``event`` field.
- Key *values* are never written to any log output.
- Rotation events are counted in Prometheus.
"""

from __future__ import annotations

import logging

from pydantic import SecretStr

from app.core.config import settings
from app.observability.metrics import secret_rotation_total
from app.secrets.schemas import KeyPair

logger = logging.getLogger(__name__)


class KeyRotationService:
    """Manages the current and previous JWT HMAC signing keys in memory."""

    def __init__(
        self,
        current_key: str,
        previous_key: str | None = None,
    ) -> None:
        if not current_key:
            raise ValueError("current_key must not be empty")
        self._current: str = current_key
        self._previous: str | None = previous_key

    # ── Accessors ──────────────────────────────────────────────────────────────

    def get_current_key(self) -> str:
        """Return the current signing key (plain string for PyJWT)."""
        return self._current

    def get_previous_key(self) -> str | None:
        """Return the previous key, or ``None`` if none is retained."""
        return self._previous

    def get_keypair(self) -> KeyPair:
        """Return a ``KeyPair`` with ``SecretStr`` fields — safe for logging."""
        return KeyPair(
            current=SecretStr(self._current),
            previous=SecretStr(self._previous) if self._previous is not None else None,
        )

    # ── Rotation operations ────────────────────────────────────────────────────

    def promote_new_key(self, new_key: str) -> None:
        """Rotate to *new_key* without downtime.

        After this call:
        - ``get_current_key()`` returns *new_key* (signing uses this).
        - ``get_previous_key()`` returns the old current key (verification
          still accepts it so outstanding tokens are not invalidated).
        """
        if not new_key:
            raise ValueError("new_key must not be empty")
        self._previous = self._current
        self._current = new_key
        logger.info(
            "JWT key rotation: new key promoted; old key retained as previous",
            extra={"event": "key_promoted"},
        )
        secret_rotation_total.labels(event="promoted").inc()

    def retire_old_key(self) -> None:
        """Remove the previous key.

        Call this only after all tokens signed with the previous key have
        expired (i.e. after at least ``JWT_EXPIRY_SECONDS`` have passed since
        the last ``promote_new_key`` call).  This is a no-op when there is no
        previous key.
        """
        if self._previous is None:
            return
        self._previous = None
        logger.info(
            "JWT key rotation: previous key retired",
            extra={"event": "key_retired"},
        )
        secret_rotation_total.labels(event="retired").inc()


# ---------------------------------------------------------------------------
# Module-level singleton — initialised lazily from settings.
#
# Tests that need isolated rotation state should construct their own
# KeyRotationService and pass it to validate_token() directly — do NOT
# monkeypatch the module-level _default_service in parallel test suites.
# ---------------------------------------------------------------------------

_default_service: KeyRotationService | None = None


def get_rotation_service() -> KeyRotationService:
    """Return (or lazily create) the process-wide KeyRotationService."""
    global _default_service
    if _default_service is None:
        prev = settings.JWT_PREVIOUS_SECRET if settings.JWT_PREVIOUS_SECRET else None
        _default_service = KeyRotationService(
            current_key=settings.JWT_SECRET,
            previous_key=prev,
        )
    return _default_service
