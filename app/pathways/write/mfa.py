from abc import ABC, abstractmethod
from uuid import UUID


class MFAProvider(ABC):
    @abstractmethod
    async def request_challenge(self, user_id: UUID, tenant_id: UUID) -> str: ...

    @abstractmethod
    async def verify_challenge(self, user_id: UUID, challenge_token: str) -> bool: ...


class MockMFAProvider(MFAProvider):
    """Always-pass implementation for development and testing."""

    async def request_challenge(self, user_id: UUID, tenant_id: UUID) -> str:
        return f"mock-challenge-{user_id}"

    async def verify_challenge(self, user_id: UUID, challenge_token: str) -> bool:
        return True
