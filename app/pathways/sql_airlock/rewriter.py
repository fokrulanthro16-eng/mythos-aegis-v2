from __future__ import annotations

from sqlglot import exp

from app.core.exceptions import SqlAirlockViolation

_MAX_LIMIT: int = 100


def _build_tenant_predicate() -> exp.EQ:
    return exp.EQ(
        this=exp.Column(this=exp.Identifier(this="user_id")),
        expression=exp.Placeholder(this="session_user_id"),
    )


def _is_user_id_eq(condition: exp.Expression) -> bool:
    if not isinstance(condition, exp.EQ):
        return False
    left, right = condition.this, condition.expression
    return (isinstance(left, exp.Column) and left.name.lower() == "user_id") or (
        isinstance(right, exp.Column) and right.name.lower() == "user_id"
    )


def _strip_user_id(condition: exp.Expression) -> exp.Expression | None:
    """Remove user_id = ... predicates from an AND-chain.

    Returns None if the whole condition was user_id predicates.
    Raises SqlAirlockViolation if user_id appears in an unsupported context
    (inside an OR, NOT, subquery, etc.).
    """
    if _is_user_id_eq(condition):
        return None

    if isinstance(condition, exp.And):
        left = _strip_user_id(condition.this)
        right = _strip_user_id(condition.expression)
        if left is None and right is None:
            return None
        if left is None:
            return right
        if right is None:
            return left
        return exp.And(this=left, expression=right)

    # Any other expression type: block if user_id hides inside it.
    for col in condition.find_all(exp.Column):
        if col.name.lower() == "user_id":
            raise SqlAirlockViolation(
                "user_id predicate found in an unsupported WHERE context; "
                "omit any user_id filter — it is injected automatically"
            )

    return condition


def inject_tenant_filter(select: exp.Select) -> exp.Select:
    """Inject user_id = :session_user_id into WHERE.

    Removes any user-supplied user_id predicate before injecting the forced value.
    """
    tenant_pred = _build_tenant_predicate()
    result = select.copy()

    where_raw = result.args.get("where")

    if where_raw is None:
        result.set("where", exp.Where(this=tenant_pred))
        return result

    if not isinstance(where_raw, exp.Where):
        result.set("where", exp.Where(this=tenant_pred))
        return result

    cleaned = _strip_user_id(where_raw.this)
    if cleaned is None:
        result.set("where", exp.Where(this=tenant_pred))
    else:
        result.set(
            "where", exp.Where(this=exp.And(this=cleaned, expression=tenant_pred))
        )

    return result


def enforce_limit(select: exp.Select) -> exp.Select:
    """Ensure LIMIT is present and does not exceed 100."""
    result = select.copy()
    lim_raw = result.args.get("limit")

    if lim_raw is None:
        result.set("limit", exp.Limit(expression=exp.Literal.number(_MAX_LIMIT)))
        return result

    if not isinstance(lim_raw, exp.Limit):
        result.set("limit", exp.Limit(expression=exp.Literal.number(_MAX_LIMIT)))
        return result

    val_expr = lim_raw.expression
    try:
        current = int(val_expr.this)
    except (AttributeError, TypeError, ValueError):
        current = _MAX_LIMIT + 1

    if current > _MAX_LIMIT:
        result.set("limit", exp.Limit(expression=exp.Literal.number(_MAX_LIMIT)))

    return result


def rewrite(select: exp.Select) -> str:
    """Apply tenant filter injection and LIMIT enforcement; return final SQL."""
    result = inject_tenant_filter(select)
    result = enforce_limit(result)
    return result.sql()
