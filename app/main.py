from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, field_validator

from app.agent.routes import router as agent_router
from app.auth.dependencies import get_security_context
from app.auth.middleware import JWTAuthMiddleware
from app.billing.routes import router as billing_router
from app.core.errors import (
    IntentParseError,
    SecurityViolationError,
    intent_parse_error_handler,
    security_violation_handler,
)
from app.core.logging import configure_logging
from app.core.security_context import SecurityContext
from app.intent.parser import parse
from app.intent.schemas import IntentParseResult
from app.observability.health import ops_router
from app.observability.health import router as health_router
from app.observability.middleware import ObservabilityMiddleware
from app.observability.tracing import setup_tracing
from app.orchestrator import route
from app.rag.routes import router as rag_router
from app.rate_limit.limiter import close_redis
from app.rate_limit.middleware import RateLimitMiddleware
from app.response.schemas import ResponsePayload
from app.vision.routes import router as vision_router
from app.workflow.routes import router as workflow_router

# Type alias for the authenticated security context dependency.
_SecurityCtx = Annotated[SecurityContext, Depends(get_security_context)]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    setup_tracing(_app)
    yield
    await close_redis()


app = FastAPI(
    title="Mythos Aegis",
    description=(
        "AI SaaS platform with RAG, Vision, Agent, Billing, and Workflow. "
        "All requests are routed through pathway-specific guardrails."
    ),
    version="0.4.0",
    lifespan=lifespan,
)

# Middleware stack (last add_middleware call becomes outermost — runs first):
#   CORSMiddleware           ← outermost: preflight before JWT blocks OPTIONS
#   ObservabilityMiddleware  ← sets request_id, records metrics
#   JWTAuthMiddleware        ← validates JWT, sets security_context
#   RateLimitMiddleware      ← innermost: reads security_context, enforces limits
app.add_middleware(RateLimitMiddleware)
app.add_middleware(JWTAuthMiddleware)
app.add_middleware(ObservabilityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(IntentParseError, intent_parse_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(SecurityViolationError, security_violation_handler)  # type: ignore[arg-type]

app.include_router(ops_router)
app.include_router(health_router)
app.include_router(rag_router)
app.include_router(vision_router)
app.include_router(agent_router)
app.include_router(workflow_router)
app.include_router(billing_router)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ParseRequest(BaseModel):
    text: str


class RouteRequest(BaseModel):
    """Authenticated route request.

    The security_context is derived from the Bearer JWT in the Authorization
    header — it is not accepted from the request body.
    """

    message: str

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be blank")
        return v


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------



@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/intent/parse", response_model=IntentParseResult)
async def parse_intent(req: ParseRequest) -> IntentParseResult:
    try:
        return parse(req.text)
    except ValueError as exc:
        raise IntentParseError(str(exc)) from exc


@app.post("/v1/route", response_model=ResponsePayload)
async def route_message(
    req: RouteRequest,
    ctx: _SecurityCtx,
) -> ResponsePayload:
    """Parse the user message and route it through the appropriate pathway.

    Authentication: Bearer JWT required (validated by JWTAuthMiddleware).
    Authorization: enforced inside the orchestrator based on action type.
    """
    try:
        parse_result = parse(req.message)
    except ValueError as exc:
        raise IntentParseError(str(exc)) from exc
    return await route(parse_result, ctx)
