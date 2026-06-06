"""Secret manager — validation, key-pair retrieval, and audit logging.

Validation rules
----------------
- ``development`` / ``staging``: all values pass so local secrets work.
- ``production``: blank, too-short, and known-default values are rejected.
- Failures are counted in Prometheus and logged by *name* only — the secret
  *value* is never written to any log output.
"""

from __future__ import annotations

import logging

from pydantic import SecretStr

from app.core.config import _DEV_JWT_PLACEHOLDER, settings
from app.observability.metrics import secret_validation_failures_total
from app.secrets.provider import EnvironmentSecretProvider, SecretProvider
from app.secrets.schemas import KeyPair

logger = logging.getLogger(__name__)

_MIN_KEY_LEN: int = 32
_DEV_DEFAULTS: frozenset[str] = frozenset({_DEV_JWT_PLACEHOLDER})


class SecretManager:
    """Facade over a ``SecretProvider`` with production validation."""

    def __init__(self, provider: SecretProvider | None = None) -> None:
        self._provider: SecretProvider = provider or EnvironmentSecretProvider()

    # ── Key retrieval ──────────────────────────────────────────────────────────

    def get_jwt_keypair(self) -> KeyPair:
        """Return the current (and optionally previous) JWT signing keys.

        Reads ``JWT_SECRET`` and ``JWT_PREVIOUS_SECRET`` from the provider.
        An absent or empty ``JWT_PREVIOUS_SECRET`` means no previous key is
        configured (normal state before the first rotation).
        """
        current_secret = self._provider.get_secret("JWT_SECRET")
        prev_secret = self._provider.get_secret("JWT_PREVIOUS_SECRET")
        prev_raw = prev_secret.value.get_secret_value()
        return KeyPair(
            current=current_secret.value,
            previous=SecretStr(prev_raw) if prev_raw else None,
        )

    # ── Validation ─────────────────────────────────────────────────────────────

    def validate_secret(
        self,
        name: str,
        value: str,
        *,
        env: str | None = None,
    ) -> None:
        """Validate *value* for secret *name* in the given environment.

        ``env`` defaults to ``settings.APP_ENV`` when not supplied.
        Non-production environments always pass — this allows local dev
        secrets and CI test tokens without changes.

        Raises ``ValueError`` on failure.  The secret *value* is never
        included in the exception message or log output.
        """
        effective_env = env if env is not None else settings.APP_ENV
        if effective_env != "production":
            return

        if not value:
            self._record_failure(name, "missing")
            raise ValueError(
                f"Secret {name!r} is required in production but was not provided."
            )
        if value in _DEV_DEFAULTS:
            self._record_failure(name, "default_value")
            raise ValueError(
                f"Secret {name!r} must not use the default development value "
                "in production."
            )
        if len(value) < _MIN_KEY_LEN:
            self._record_failure(name, "too_short")
            raise ValueError(
                f"Secret {name!r} must be ≥{_MIN_KEY_LEN} characters in production "
                f"(got {len(value)})."
            )

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _record_failure(self, name: str, reason: str) -> None:
        """Increment the metric and emit a warning — never logs the value."""
        secret_validation_failures_total.labels(reason=reason).inc()
        logger.warning(
            "Secret validation failed: name=%r reason=%s env=production",
            name,
            reason,
        )
