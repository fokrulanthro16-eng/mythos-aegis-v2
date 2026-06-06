from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.core.security_context import SecurityContext


def _make(
    *,
    request_id: UUID | None = None,
    current_user_id: UUID | None = None,
    tenant_id: UUID | None = None,
    roles: frozenset[str] | None = None,
    permissions: frozenset[str] | None = None,
) -> SecurityContext:
    return SecurityContext(
        request_id=request_id or uuid4(),
        current_user_id=current_user_id or uuid4(),
        tenant_id=tenant_id or uuid4(),
        roles=roles if roles is not None else frozenset(["admin"]),
        permissions=permissions if permissions is not None else frozenset(["read"]),
    )


def test_valid_construction() -> None:
    ctx = _make()
    assert isinstance(ctx.request_id, UUID)
    assert isinstance(ctx.roles, frozenset)
    assert isinstance(ctx.permissions, frozenset)


def test_immutability() -> None:
    ctx = _make()
    with pytest.raises(ValidationError):
        ctx.request_id = uuid4()  # type: ignore[misc]


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        SecurityContext(
            request_id=uuid4(),
            current_user_id=uuid4(),
            tenant_id=uuid4(),
            roles=frozenset(),
            permissions=frozenset(),
            bad_field="oops",  # type: ignore[call-arg]
        )


def test_roles_as_frozenset() -> None:
    ctx = _make(roles=frozenset(["admin", "viewer"]))
    assert "admin" in ctx.roles
    assert isinstance(ctx.roles, frozenset)


def test_empty_roles_and_permissions() -> None:
    ctx = _make(roles=frozenset(), permissions=frozenset())
    assert ctx.roles == frozenset()
    assert ctx.permissions == frozenset()


def test_uuid_field_values() -> None:
    rid = uuid4()
    uid = uuid4()
    tid = uuid4()
    ctx = SecurityContext(
        request_id=rid,
        current_user_id=uid,
        tenant_id=tid,
        roles=frozenset(),
        permissions=frozenset(),
    )
    assert ctx.request_id == rid
    assert ctx.current_user_id == uid
    assert ctx.tenant_id == tid


def test_permissions_as_frozenset() -> None:
    ctx = _make(permissions=frozenset(["read", "write", "delete"]))
    assert "write" in ctx.permissions
    assert isinstance(ctx.permissions, frozenset)
