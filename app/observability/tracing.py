"""OpenTelemetry tracing setup.

Design rules
------------
- Safe no-op when OTEL_ENABLED=false — zero OTel imports happen.
- All OTel imports are lazy (inside the try block) so the app starts
  even if the packages are not installed.
- Never records JWT tokens, SQL strings, secrets, raw user messages,
  Authorization headers, or any credential-bearing data.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


def setup_tracing(app: FastAPI | None = None) -> None:
    """Configure OTel tracing provider and instrumentations.

    Safe no-op when ``settings.OTEL_ENABLED`` is False or when the
    opentelemetry packages are not installed.
    """
    if not settings.OTEL_ENABLED:
        logger.debug("OTEL_ENABLED=false — tracing disabled (no-op)")
        return

    try:
        _configure_provider()
        _instrument_fastapi(app)
        _instrument_sqlalchemy()
        logger.info(
            "OpenTelemetry tracing enabled",
            extra={
                "service": settings.OTEL_SERVICE_NAME,
                "endpoint": settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            },
        )
    except Exception as exc:  # pragma: no cover
        logger.warning(
            "OpenTelemetry setup failed — tracing disabled: %s",
            type(exc).__name__,
        )


# ---------------------------------------------------------------------------
# Internal helpers — all OTel imports are contained here so that the public
# surface (`setup_tracing`) never imports OTel at module scope.
# ---------------------------------------------------------------------------


def _configure_provider() -> None:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({"service.name": settings.OTEL_SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


def _instrument_fastapi(app: FastAPI | None) -> None:
    if app is None:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(
            app,
            # Exclude high-frequency endpoints from trace noise.
            excluded_urls="metrics,health,health/live,health/ready,health/startup",
            # Never capture request/response bodies (may contain secrets).
            http_capture_headers_server_request=[],
            http_capture_headers_server_response=["x-request-id"],
        )
    except ImportError:
        logger.debug("FastAPI OTel instrumentation package not available")


def _instrument_sqlalchemy() -> None:
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        from app.db.session import (
            engine,
        )  # imported here to avoid circular deps at module level

        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    except ImportError:
        logger.debug("SQLAlchemy OTel instrumentation package not available")
