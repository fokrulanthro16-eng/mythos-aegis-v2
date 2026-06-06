import logging

import sqlglot
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError, MythosError, SqlAirlockViolation
from app.core.result import Failure, Result, Success
from app.pathways.sql_airlock.executor import execute_analytics
from app.pathways.sql_airlock.rewriter import rewrite
from app.pathways.sql_airlock.schemas import AnalyticsRequest, AnalyticsResponse
from app.pathways.sql_airlock.validator import validate

logger = logging.getLogger(__name__)


async def execute_analytics_query(
    request: AnalyticsRequest,
    session: AsyncSession,
) -> Result[AnalyticsResponse]:
    """Orchestrate: validate → rewrite → reparse → execute.

    All failures are returned as Failure; no exception escapes the boundary.
    """
    try:
        # Step 1: validate (lexical + structural + semantic rules)
        ast = validate(request.sql)

        # Step 2: rewrite (tenant filter injection + LIMIT enforcement)
        rewritten_sql = rewrite(ast)

        # Step 3: reparse — abort if the rewrite produced structurally invalid SQL
        try:
            sqlglot.parse_one(rewritten_sql)
        except sqlglot.errors.ParseError as exc:
            raise SqlAirlockViolation(
                f"Rewritten SQL failed structural validation: {exc}"
            ) from exc

        # Step 4: execute with parameterized binding
        exec_result = await execute_analytics(
            rewritten_sql,
            session_user_id=request.user_id,
            session=session,
        )

        if isinstance(exec_result, Failure):
            return exec_result

        rows = exec_result.value
        return Success(value=AnalyticsResponse(rows=rows, row_count=len(rows)))

    except MythosError as exc:
        return Failure(error=exc, message=exc.message)
    except Exception:
        logger.exception("Unexpected error in analytics pipeline")
        return Failure(
            error=DatabaseError("Analytics pipeline failed"),
            message="A system error occurred",
        )
