"""Value objects for the secrets layer.

``SecretStr`` (pydantic) is used for any field that holds secret material —
it masks the value in ``__repr__`` and JSON serialisation, preventing
accidental log or audit-trail exposure.  Access the raw value only where
strictly necessary with ``.get_secret_value()``.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, SecretStr


class SecretMetadata(BaseModel):
    """Non-sensitive metadata describing a stored secret."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str  # "env", a UUID, a version ARN, a UNIX timestamp, etc.
    created_at: datetime
    last_rotated_at: datetime | None = None


class SecretValue(BaseModel):
    """A secret value paired with its metadata.

    ``value`` is a ``SecretStr`` — the raw bytes are never emitted to
    repr, logs, or JSON.  Call ``value.get_secret_value()`` only where
    the raw material is genuinely required.
    """

    model_config = ConfigDict(frozen=True)

    metadata: SecretMetadata
    value: SecretStr


class KeyPair(BaseModel):
    """Current and (optionally) previous JWT signing key.

    Both fields are ``SecretStr`` so key material never appears in logs.
    ``previous`` is ``None`` when no previous key is configured — i.e. before
    the first rotation or after the previous key has been retired.
    """

    model_config = ConfigDict(frozen=True)

    current: SecretStr
    previous: SecretStr | None = None
