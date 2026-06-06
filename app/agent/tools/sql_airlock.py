"""SQL Airlock tool — safe, read-only SQL execution with validation.

Security guarantees:
- Only SELECT statements are accepted (validated by sqlglot parser).
- Secondary keyword blocklist as defense-in-depth.
- Results bounded to _MAX_ROWS rows.
- All executions are logged (SQL char count only, never content).
- Execution errors return a safe message without leaking schema details.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.base import BaseTool, ToolDefinition, ToolParameter, ToolResult
from app.core.exceptions import SqlAirlockViolation
from app.core.security_context import SecurityContext

logger = logging.getLogger(__name__)

_NAME = "sql_query"
_MAX_ROWS = 50

_BLOCKED_KEYWORDS = frozenset(
    {
        "insert",
        "update",
        "delete",
        "drop",
        "create",
        "alter",
        "truncate",
        "grant",
        "revoke",
        "execute",
        "exec(",
        "xp_",
        "sp_",
    }
)


def _validate_select_only(sql: str) -> None:
    """Raise SqlAirlockViolation if sql is not a pure SELECT."""
    import sqlglot

    if not sql.strip():
        raise SqlAirlockViolation("Empty SQL statement")

    try:
        statements = [
            s for s in sqlglot.parse(sql, dialect="postgres") if s is not None
        ]
    except Exception as exc:
        raise SqlAirlockViolation("SQL parse error") from exc

    if not statements:
        raise SqlAirlockViolation("Empty SQL statement")

    for stmt in statements:
        if stmt is None:
            continue
        if type(stmt).__name__.lower() != "select":
            raise SqlAirlockViolation(
                f"Only SELECT statements are allowed (got {type(stmt).__name__})"
            )

    lowered = sql.lower()
    for kw in _BLOCKED_KEYWORDS:
        if kw in lowered:
            raise SqlAirlockViolation("Blocked keyword in SQL")


class SQLAirlockTool(BaseTool):
    """Execute a read-only SQL SELECT through the security airlock."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=_NAME,
            description=(
                "Execute a safe, read-only SQL SELECT query against the database. "
                "Returns up to 50 rows. Only SELECT statements are allowed. "
                "Use for analytics, counting records, or structured data lookups."
            ),
            parameters=[
                ToolParameter(
                    "sql",
                    "string",
                    "The SQL SELECT statement to execute",
                    required=True,
                ),
            ],
            required_permission="analytics.read",
        )

    async def execute(
        self,
        params: dict[str, Any],
        ctx: SecurityContext,
        session: AsyncSession,
    ) -> ToolResult:
        sql: str = str(params.get("sql", "")).strip()

        if not sql:
            return ToolResult(success=False, data=None, error="sql is required")
        if "analytics.read" not in ctx.permissions:
            return ToolResult(
                success=False, data=None, error="Permission 'analytics.read' required"
            )

        try:
            _validate_select_only(sql)
        except SqlAirlockViolation as exc:
            logger.warning(
                "tool.sql_airlock.blocked tenant=%s reason=%s",
                ctx.tenant_id,
                exc.message,
            )
            return ToolResult(
                success=False, data=None, error=f"SQL blocked: {exc.message}"
            )

        safe_sql = f"SELECT * FROM ({sql}) AS _agent_q LIMIT {_MAX_ROWS}"  # nosec B608

        try:
            result = await session.execute(text(safe_sql))
            columns = list(result.keys())
            rows = [
                {
                    col: str(val) if val is not None else None
                    for col, val in zip(columns, row, strict=False)
                }
                for row in result.fetchall()
            ]
        except SQLAlchemyError:
            logger.warning(
                "tool.sql_airlock.exec_error tenant=%s sql_chars=%d",
                ctx.tenant_id,
                len(sql),
            )
            return ToolResult(
                success=False,
                data=None,
                error="SQL execution error — check your query syntax",
            )

        logger.info(
            "tool.sql_airlock.executed tenant=%s rows=%d sql_chars=%d",
            ctx.tenant_id,
            len(rows),
            len(sql),
        )
        return ToolResult(
            success=True,
            data={"columns": columns, "rows": rows, "row_count": len(rows)},
        )
