from dataclasses import dataclass
from typing import final


@final
@dataclass(frozen=True)
class Success[T]:
    value: T


@final
@dataclass(frozen=True)
class Failure:
    error: Exception
    message: str = ""


type Result[T] = Success[T] | Failure
