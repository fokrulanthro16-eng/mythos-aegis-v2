"""Tests for app.core.config — Settings validation and production hardening."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import _DEV_JWT_PLACEHOLDER, _MIN_PRODUCTION_SECRET_LEN, Settings

# ── Module-level singleton sanity check ───────────────────────────────────────


def test_default_settings_load() -> None:
    """The module-level singleton initialises without raising."""
    from app.core.config import settings

    assert settings.APP_ENV in {"development", "staging", "production"}


# ── APP_ENV validation ─────────────────────────────────────────────────────────


def test_valid_app_envs_accepted() -> None:
    for env in ("development", "staging", "production"):
        if env == "production":
            # production also needs a strong secret
            s = Settings(APP_ENV=env, JWT_SECRET="x" * _MIN_PRODUCTION_SECRET_LEN)
        else:
            s = Settings(APP_ENV=env)
        assert env == s.APP_ENV


def test_invalid_app_env_rejected() -> None:
    with pytest.raises(ValidationError, match="APP_ENV"):
        Settings(APP_ENV="testing")


# ── JWT field presence ─────────────────────────────────────────────────────────


def test_required_jwt_fields_have_defaults() -> None:
    s = Settings(APP_ENV="development")
    assert s.JWT_SECRET == _DEV_JWT_PLACEHOLDER
    assert s.JWT_ALGORITHM == "HS256"
    assert s.JWT_ISSUER == "mythos-aegis"
    assert s.JWT_AUDIENCE == "mythos-aegis-api"
    assert s.JWT_EXPIRY_SECONDS == 3600


# ── Production JWT secret validation ──────────────────────────────────────────


def test_production_rejects_default_jwt_secret() -> None:
    """The known dev secret must be rejected in production."""
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(APP_ENV="production", JWT_SECRET=_DEV_JWT_PLACEHOLDER)


def test_production_rejects_short_jwt_secret() -> None:
    """A secret shorter than the minimum must be rejected in production."""
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(APP_ENV="production", JWT_SECRET="tooshort")


def test_production_rejects_31_char_secret() -> None:
    """One character below the minimum is still rejected."""
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(
            APP_ENV="production", JWT_SECRET="a" * (_MIN_PRODUCTION_SECRET_LEN - 1)
        )


def test_production_accepts_minimum_length_strong_secret() -> None:
    """Exactly _MIN_PRODUCTION_SECRET_LEN chars (not the default) is accepted."""
    s = Settings(
        APP_ENV="production",
        JWT_SECRET="a" * _MIN_PRODUCTION_SECRET_LEN,
    )
    assert s.APP_ENV == "production"


def test_production_accepts_long_custom_secret() -> None:
    strong = "super-secret-production-key-that-is-long-enough-to-be-secure"
    s = Settings(APP_ENV="production", JWT_SECRET=strong)
    assert strong == s.JWT_SECRET


def test_development_allows_default_jwt_secret() -> None:
    """The default dev secret is acceptable when APP_ENV=development."""
    s = Settings(APP_ENV="development", JWT_SECRET=_DEV_JWT_PLACEHOLDER)
    assert s.JWT_SECRET == _DEV_JWT_PLACEHOLDER


def test_staging_allows_default_jwt_secret() -> None:
    """The default dev secret is allowed in staging (warned, not rejected)."""
    s = Settings(APP_ENV="staging", JWT_SECRET=_DEV_JWT_PLACEHOLDER)
    assert s.APP_ENV == "staging"


# ── Other field validators ─────────────────────────────────────────────────────


def test_confidence_threshold_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(INTENT_CONFIDENCE_THRESHOLD=0.0)


def test_confidence_threshold_above_one_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(INTENT_CONFIDENCE_THRESHOLD=1.1)


def test_confidence_threshold_one_accepted() -> None:
    s = Settings(INTENT_CONFIDENCE_THRESHOLD=1.0)
    assert s.INTENT_CONFIDENCE_THRESHOLD == 1.0


def test_sql_timeout_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(SQL_TIMEOUT_SECONDS=0)


def test_sql_timeout_over_max_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(SQL_TIMEOUT_SECONDS=31)


def test_sql_max_limit_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(SQL_MAX_LIMIT=0)


def test_sql_max_limit_over_cap_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(SQL_MAX_LIMIT=1001)


# ── Alembic migration smoke test (no real DB required) ────────────────────────


def test_alembic_initial_migration_structure() -> None:
    """Verify the initial migration file is importable and has the expected shape."""
    import importlib.util
    from pathlib import Path

    mig_path = (
        Path(__file__).parent.parent.parent
        / "alembic"
        / "versions"
        / "aef8c3b72d1a_initial_schema.py"
    )
    assert mig_path.exists(), f"Migration file not found: {mig_path}"

    spec = importlib.util.spec_from_file_location("migration_initial", mig_path)
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "aef8c3b72d1a"
    assert migration.down_revision is None
    assert migration.branch_labels is None
    assert migration.depends_on is None
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)
