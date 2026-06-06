import logging
import sys
from typing import Any

from pythonjsonlogger.json import JsonFormatter

from app.core.config import settings

_LOG_FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


def configure_logging(**_: Any) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT))

    level = logging.DEBUG if settings.APP_ENV == "development" else logging.INFO

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    logging.getLogger("uvicorn.access").propagate = False
