from __future__ import annotations

import re
from datetime import date
from typing import cast

import sqlglot
from sqlglot import exp

from app.core.exceptions import SqlAirlockViolation
from app.pathways.sql_airlock.metadata import ALLOWED_TABLES, BLOCKED_COLUMNS

_BLOCKED_LEXICAL: tuple[str, ...] = ("--", "/*", "*/", ";", "\x00")
_DATE_PATTERN: re.Pattern[str] = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def _check_lexical(sql: str) -> None:
    for token in _BLOCKED_LEXICAL:
        if token in sql:
            raise SqlAirlockViolation(f"Forbidden pattern in SQL: {token!r}")


def _check_statement_type(tree: object) -> None:
    if not isinstance(tree, exp.Select):
        kind = type(tree).__name__
        raise SqlAirlockViolation(f"Only SELECT statements are allowed; got {kind}")


def _check_tables(tree: exp.Select) -> None:
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        if name and name not in ALLOWED_TABLES:
            raise SqlAirlockViolation(f"Table '{name}' is not in the allowed registry")


def _check_columns(tree: exp.Select) -> None:
    for sel in tree.selects:
        if isinstance(sel, exp.Star):
            raise SqlAirlockViolation("SELECT * is not allowed")
        if isinstance(sel, exp.Column) and isinstance(sel.this, exp.Star):
            raise SqlAirlockViolation("SELECT * is not allowed")

    for col in tree.find_all(exp.Column):
        name = col.name.lower()
        if name in BLOCKED_COLUMNS:
            raise SqlAirlockViolation(f"Column '{name}' is not permitted")


def _check_temporal_boundary(sql: str) -> None:
    dates: list[date] = []
    for match in _DATE_PATTERN.finditer(sql):
        raw = match.group(1)
        try:
            dates.append(date.fromisoformat(raw))
        except ValueError:
            raise SqlAirlockViolation(f"Malformed date literal: {raw!r}") from None

    if len(dates) >= 2:
        dates.sort()
        span = (dates[-1] - dates[0]).days
        if span > 90:
            raise SqlAirlockViolation(
                f"Date window of {span} days exceeds the 90-day maximum"
            )


def validate(sql: str) -> exp.Select:
    """Parse and validate SQL against all airlock rules.

    Returns the parsed AST on success.
    Raises SqlAirlockViolation on any violation.
    """
    _check_lexical(sql)

    try:
        tree = sqlglot.parse_one(sql)
    except sqlglot.errors.ParseError as exc:
        raise SqlAirlockViolation(f"SQL parse error: {exc}") from exc

    _check_statement_type(tree)
    select = cast(exp.Select, tree)

    _check_tables(select)
    _check_columns(select)
    _check_temporal_boundary(sql)

    return select
