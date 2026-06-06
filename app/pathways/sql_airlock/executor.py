import asyncio
import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError, SqlAirlockViolation
from app.core.result import Failure, Result, Success

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS: float = 3.0


async def _run_query(
    sql: str,
    *,
    session_user_id: UUID,
    session: AsyncSession,
) -> list[dict[str, object]]:
    stmt = text(sql).bindparams(session_user_id=str(session_user_id))
    db_result = await session.execute(stmt)
    rows = db_result.mappings().all()
    return [dict(row) for row in rows]


async def execute_analytics(
    sql: str,
    *,
    session_user_id: UUID,
    session: AsyncSession,
) -> Result[list[dict[str, object]]]:
    """Execute a validated, rewritten analytics query.

    Binds :session_user_id as a parameter — never interpolates values.
    Enforces a 3-second execution timeout.
    Never exposes raw database exceptions.
    """
    try:
        rows = await asyncio.wait_for(
            _run_query(sql, session_user_id=session_user_id, session=session),
            timeout=_TIMEOUT_SECONDS,
        )
        return Success(value=rows)
    except TimeoutError:
        logger.error("Analytics query exceeded %.1f second timeout", _TIMEOUT_SECONDS)
        return Failure(
            error=SqlAirlockViolation("Query timed out"),
            message="Query exceeded the maximum execution time",
        )
    except Exception:
        logger.exception("Analytics query execution failed")
        return Failure(
            error=DatabaseError("Query execution failed"),
            message="A system error occurred during query execution",
        )
