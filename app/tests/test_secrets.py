"""Tests for app/secrets/ — provider, schemas, and SecretManager."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from app.secrets.manager import _DEV_DEFAULTS, _MIN_KEY_LEN, SecretManager
from app.secrets.provider import (
    AWSSecretsManagerProvider,
    AzureKeyVaultProvider,
    EnvironmentSecretProvider,
    VaultSecretProvider,
)
from app.secrets.schemas import KeyPair, SecretMetadata, SecretValue

# ---------------------------------------------------------------------------
# SecretMetadata and SecretValue
# ---------------------------------------------------------------------------


def test_secret_metadata_fields() -> None:
    from datetime import UTC, datetime

    meta = SecretMetadata(name="MY_KEY", version="v1", created_at=datetime.now(UTC))
    assert meta.name == "MY_KEY"
    assert meta.version == "v1"
    assert meta.last_rotated_at is None


def test_secret_value_masks_in_repr() -> None:
    """SecretStr must never expose the raw value in repr or str."""
    from datetime import UTC, datetime

    from pydantic import SecretStr

    sv = SecretValue(
        metadata=SecretMetadata(
            name="KEY", version="env", created_at=datetime.now(UTC)
        ),
        value=SecretStr("super-secret-value"),
    )
    rep = repr(sv)
    assert "super-secret-value" not in rep
    # The SecretStr placeholder should appear
    assert "**" in rep


def test_secret_value_accessible_via_get_secret_value() -> None:
    from datetime import UTC, datetime

    from pydantic import SecretStr

    sv = SecretValue(
        metadata=SecretMetadata(
            name="KEY", version="env", created_at=datetime.now(UTC)
        ),
        value=SecretStr("raw-value"),
    )
    assert sv.value.get_secret_value() == "raw-value"


def test_key_pair_masks_both_keys_in_repr() -> None:
    from pydantic import SecretStr

    kp = KeyPair(current=SecretStr("key-a"), previous=SecretStr("key-b"))
    rep = repr(kp)
    assert "key-a" not in rep
    assert "key-b" not in rep


def test_key_pair_previous_optional() -> None:
    from pydantic import SecretStr

    kp = KeyPair(current=SecretStr("only-key"))
    assert kp.previous is None


# ---------------------------------------------------------------------------
# EnvironmentSecretProvider
# ---------------------------------------------------------------------------


def test_env_provider_reads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_MY_SECRET", "hello-world")
    provider = EnvironmentSecretProvider()
    sv = provider.get_secret("TEST_MY_SECRET")
    assert sv.value.get_secret_value() == "hello-world"
    assert sv.metadata.name == "TEST_MY_SECRET"
    assert sv.metadata.version == "env"


def test_env_provider_returns_empty_for_missing_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_ABSENT_VAR", raising=False)
    provider = EnvironmentSecretProvider()
    sv = provider.get_secret("TEST_ABSENT_VAR")
    assert sv.value.get_secret_value() == ""


def test_env_provider_version_is_env() -> None:
    provider = EnvironmentSecretProvider()
    assert provider.get_secret_version("ANYTHING") == "env"


def test_env_provider_secret_value_not_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENSITIVE_KEY", "mysupersecret")
    provider = EnvironmentSecretProvider()
    sv = provider.get_secret("SENSITIVE_KEY")
    # Raw value must not appear anywhere in the object representation
    assert "mysupersecret" not in repr(sv)
    assert "mysupersecret" not in str(sv)


# ---------------------------------------------------------------------------
# Future-compatible stubs raise NotImplementedError
# ---------------------------------------------------------------------------


def test_vault_provider_raises_not_implemented() -> None:
    provider = VaultSecretProvider()
    with pytest.raises(NotImplementedError):
        provider.get_secret("ANY")


def test_aws_provider_raises_not_implemented() -> None:
    provider = AWSSecretsManagerProvider()
    with pytest.raises(NotImplementedError):
        provider.get_secret("ANY")


def test_azure_provider_raises_not_implemented() -> None:
    provider = AzureKeyVaultProvider()
    with pytest.raises(NotImplementedError):
        provider.get_secret("ANY")


# ---------------------------------------------------------------------------
# SecretManager — production validation
# ---------------------------------------------------------------------------


def test_validate_secret_passes_for_development() -> None:
    """Any value — even blank — passes in development mode."""
    manager = SecretManager()
    manager.validate_secret("JWT_SECRET", "", env="development")  # no exception


def test_validate_secret_passes_for_staging() -> None:
    manager = SecretManager()
    manager.validate_secret("JWT_SECRET", "short", env="staging")  # no exception


def test_validate_secret_rejects_blank_in_production() -> None:
    manager = SecretManager()
    with pytest.raises(ValueError, match="not provided"):
        manager.validate_secret("JWT_SECRET", "", env="production")


def test_validate_secret_rejects_dev_default_in_production() -> None:
    manager = SecretManager()
    dev_default = next(iter(_DEV_DEFAULTS))
    with pytest.raises(ValueError, match="default development value"):
        manager.validate_secret("JWT_SECRET", dev_default, env="production")


def test_validate_secret_rejects_short_key_in_production() -> None:
    manager = SecretManager()
    short = "x" * (_MIN_KEY_LEN - 1)
    with pytest.raises(ValueError, match=f"≥{_MIN_KEY_LEN}"):
        manager.validate_secret("JWT_SECRET", short, env="production")


def test_validate_secret_accepts_strong_key_in_production() -> None:
    manager = SecretManager()
    strong = "a" * _MIN_KEY_LEN
    manager.validate_secret("JWT_SECRET", strong, env="production")  # no exception


def test_validate_secret_accepts_longer_key_in_production() -> None:
    manager = SecretManager()
    manager.validate_secret("JWT_SECRET", "x" * 64, env="production")


def test_validate_secret_exactly_minimum_length_accepted() -> None:
    manager = SecretManager()
    manager.validate_secret("JWT_SECRET", "z" * _MIN_KEY_LEN, env="production")


# ---------------------------------------------------------------------------
# SecretManager — validation failure metrics & audit log
# ---------------------------------------------------------------------------


def test_validation_failure_increments_metric() -> None:
    manager = SecretManager()
    with patch("app.secrets.manager.secret_validation_failures_total") as mock_counter:
        with pytest.raises(ValueError):
            manager.validate_secret("JWT_SECRET", "", env="production")
        mock_counter.labels.assert_called()
        mock_counter.labels.return_value.inc.assert_called()


def test_validation_failure_never_logs_secret_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The secret value must never appear in log output on validation failure."""
    secret_value = "too-short"
    manager = SecretManager()
    with caplog.at_level(logging.WARNING, logger="app.secrets.manager"):  # noqa: SIM117
        with pytest.raises(ValueError):
            manager.validate_secret("JWT_SECRET", secret_value, env="production")
    for record in caplog.records:
        assert secret_value not in record.getMessage()


def test_validation_failure_logs_secret_name(caplog: pytest.LogCaptureFixture) -> None:
    """The secret *name* (not value) should appear in the warning."""
    manager = SecretManager()
    with caplog.at_level(logging.WARNING, logger="app.secrets.manager"):  # noqa: SIM117
        with pytest.raises(ValueError):
            manager.validate_secret("MY_SPECIAL_KEY", "", env="production")
    messages = [r.getMessage() for r in caplog.records]
    assert any("MY_SPECIAL_KEY" in m for m in messages)


# ---------------------------------------------------------------------------
# SecretManager — get_jwt_keypair
# ---------------------------------------------------------------------------


def test_get_jwt_keypair_returns_current_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "my-current-secret-key-value")
    monkeypatch.delenv("JWT_PREVIOUS_SECRET", raising=False)
    manager = SecretManager()
    kp = manager.get_jwt_keypair()
    assert kp.current.get_secret_value() == "my-current-secret-key-value"
    assert kp.previous is None


def test_get_jwt_keypair_includes_previous_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JWT_SECRET", "current-key-value-here")
    monkeypatch.setenv("JWT_PREVIOUS_SECRET", "old-key-value-here")
    manager = SecretManager()
    kp = manager.get_jwt_keypair()
    assert kp.current.get_secret_value() == "current-key-value-here"
    assert kp.previous is not None
    assert kp.previous.get_secret_value() == "old-key-value-here"


def test_get_jwt_keypair_masks_values_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "absolutely-secret-key-1")
    monkeypatch.setenv("JWT_PREVIOUS_SECRET", "absolutely-secret-key-2")
    manager = SecretManager()
    kp = manager.get_jwt_keypair()
    rep = repr(kp)
    assert "absolutely-secret-key-1" not in rep
    assert "absolutely-secret-key-2" not in rep
