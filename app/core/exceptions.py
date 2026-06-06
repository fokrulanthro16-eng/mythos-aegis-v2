class MythosError(Exception):
    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message


class ValidationError(MythosError):
    pass


class AuthorizationError(MythosError):
    pass


class TenantIsolationError(MythosError):
    pass


class BusinessRuleViolation(MythosError):
    pass


class SqlAirlockViolation(MythosError):
    pass


class ClarificationRequired(MythosError):
    pass


class DatabaseError(MythosError):
    pass


class AIProviderUnavailableError(MythosError):
    pass


class EmbeddingError(MythosError):
    pass


class DocumentNotFoundError(MythosError):
    pass


class FileTooLargeError(MythosError):
    pass


class UnsupportedFileTypeError(MythosError):
    pass


class AIQuotaExceededError(MythosError):
    pass


class AgentError(MythosError):
    pass


class AgentToolError(AgentError):
    pass


class AgentSessionNotFoundError(AgentError):
    pass


class AgentMaxIterationsError(AgentError):
    pass


class VisionError(MythosError):
    pass


class VisionProviderUnavailableError(VisionError):
    pass


class ImageTooLargeError(VisionError):
    pass


class BillingError(MythosError):
    pass


class BillingProviderError(BillingError):
    pass


class SubscriptionNotFoundError(BillingError):
    pass


class QuotaExceededError(BillingError):
    pass


class WorkflowError(MythosError):
    pass


class WorkflowNotFoundError(WorkflowError):
    pass


class WorkflowStepError(WorkflowError):
    pass


class WorkflowExecutionError(WorkflowError):
    pass
