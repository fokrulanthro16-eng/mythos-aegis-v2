import dataclasses

import pytest

from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleViolation,
    ClarificationRequired,
    MythosError,
    SqlAirlockViolation,
    TenantIsolationError,
    ValidationError,
)
from app.core.result import Failure, Success

# --- Result type tests ---


def test_success_holds_int_value() -> None:
    r: Success[int] = Success(value=42)
    assert r.value == 42


def test_success_holds_str_value() -> None:
    r: Success[str] = Success(value="hello")
    assert r.value == "hello"


def test_success_holds_none() -> None:
    r: Success[None] = Success(value=None)
    assert r.value is None


def test_failure_holds_error() -> None:
    err = ValidationError("bad input")
    r = Failure(error=err)
    assert r.error is err
    assert isinstance(r.error, MythosError)


def test_failure_default_message() -> None:
    r = Failure(error=MythosError("x"))
    assert r.message == ""


def test_failure_with_custom_message() -> None:
    r = Failure(error=MythosError("x"), message="detail")
    assert r.message == "detail"


def test_success_is_immutable() -> None:
    r: Success[int] = Success(value=1)
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        r.value = 99  # type: ignore[misc]


def test_failure_is_immutable() -> None:
    r = Failure(error=MythosError("x"))
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        r.message = "changed"  # type: ignore[misc]


# --- Exception hierarchy ---


def test_mythos_error_is_exception() -> None:
    err = MythosError("base")
    assert isinstance(err, Exception)
    assert err.message == "base"


def test_validation_error_inherits() -> None:
    assert issubclass(ValidationError, MythosError)
    err = ValidationError("bad")
    assert isinstance(err, MythosError)


def test_authorization_error_inherits() -> None:
    assert issubclass(AuthorizationError, MythosError)
    err = AuthorizationError("denied")
    assert isinstance(err, MythosError)


def test_tenant_isolation_error_inherits() -> None:
    assert issubclass(TenantIsolationError, MythosError)
    err = TenantIsolationError("cross-tenant")
    assert isinstance(err, MythosError)


def test_business_rule_violation_inherits() -> None:
    assert issubclass(BusinessRuleViolation, MythosError)
    err = BusinessRuleViolation("rule broken")
    assert isinstance(err, MythosError)


def test_sql_airlock_violation_inherits() -> None:
    assert issubclass(SqlAirlockViolation, MythosError)
    err = SqlAirlockViolation("unsafe SQL")
    assert isinstance(err, MythosError)


def test_clarification_required_inherits() -> None:
    assert issubclass(ClarificationRequired, MythosError)
    err = ClarificationRequired("need more info")
    assert isinstance(err, MythosError)


def test_all_subtypes_caught_as_mythos_error() -> None:
    exc_classes: tuple[type[MythosError], ...] = (
        MythosError,
        ValidationError,
        AuthorizationError,
        TenantIsolationError,
        BusinessRuleViolation,
        SqlAirlockViolation,
        ClarificationRequired,
    )
    for exc_class in exc_classes:
        with pytest.raises(MythosError):
            raise exc_class("test")
