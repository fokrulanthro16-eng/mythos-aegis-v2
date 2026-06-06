from fastapi import Request
from fastapi.responses import JSONResponse


class IntentParseError(Exception):
    def __init__(self, message: str, status_code: int = 422) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class SecurityViolationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


async def intent_parse_error_handler(
    _request: Request, exc: IntentParseError
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "intent_parse_error", "detail": exc.message},
    )


async def security_violation_handler(
    _request: Request, exc: SecurityViolationError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": "security_violation", "detail": exc.message},
    )
