"""Secret provider interface and built-in implementations.

The ``SecretProvider`` ABC decouples callers from any specific secret
backend.  Swap the concrete class in ``SecretManager`` to change where
secrets come from without touching any call sites.

Provided implementations
------------------------
- ``EnvironmentSecretProvider`` — environment variables (default, dev/CI).

Future-compatible stubs (raise NotImplementedError until wired up)
------------------------------------------------------------------
- ``VaultSecretProvider``       — HashiCorp Vault KV v2
- ``AWSSecretsManagerProvider`` — AWS Secrets Manager
- ``AzureKeyVaultProvider``     — Azure Key Vault
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from pydantic import SecretStr

from app.secrets.schemas import SecretMetadata, SecretValue


class SecretProvider(ABC):
    """Retrieve a named secret from an external or local store."""

    @abstractmethod
    def get_secret(self, name: str) -> SecretValue:
        """Return the current value of secret *name*."""

    @abstractmethod
    def get_secret_version(self, name: str) -> str:
        """Return an opaque version identifier for secret *name*."""


# ---------------------------------------------------------------------------
# Environment-variable provider (default)
# ---------------------------------------------------------------------------


class EnvironmentSecretProvider(SecretProvider):
    """Read secrets directly from environment variables.

    Variable names map 1-to-1 to secret names.  An absent variable returns
    an empty-string ``SecretValue`` — callers should treat
    ``value.get_secret_value() == ""`` as "not configured".
    """

    def get_secret(self, name: str) -> SecretValue:
        raw = os.environ.get(name, "")
        return SecretValue(
            metadata=SecretMetadata(
                name=name,
                version="env",
                created_at=datetime.now(UTC),
            ),
            value=SecretStr(raw),
        )

    def get_secret_version(self, name: str) -> str:
        return "env"


# ---------------------------------------------------------------------------
# Future-compatible stubs — raise explicitly so callers fail visibly
# ---------------------------------------------------------------------------


class VaultSecretProvider(SecretProvider):
    """HashiCorp Vault KV v2 provider — not yet implemented."""

    def get_secret(self, name: str) -> SecretValue:
        raise NotImplementedError(
            "VaultSecretProvider requires the hvac package and Vault credentials. "
            "Use EnvironmentSecretProvider for local development."
        )

    def get_secret_version(self, name: str) -> str:
        raise NotImplementedError("VaultSecretProvider is not yet implemented")


class AWSSecretsManagerProvider(SecretProvider):
    """AWS Secrets Manager provider — not yet implemented."""

    def get_secret(self, name: str) -> SecretValue:
        raise NotImplementedError(
            "AWSSecretsManagerProvider requires boto3 and IAM credentials. "
            "Use EnvironmentSecretProvider for local development."
        )

    def get_secret_version(self, name: str) -> str:
        raise NotImplementedError("AWSSecretsManagerProvider is not yet implemented")


class AzureKeyVaultProvider(SecretProvider):
    """Azure Key Vault provider — not yet implemented."""

    def get_secret(self, name: str) -> SecretValue:
        raise NotImplementedError(
            "AzureKeyVaultProvider requires azure-keyvault-secrets and AAD credentials."
        )

    def get_secret_version(self, name: str) -> str:
        raise NotImplementedError("AzureKeyVaultProvider is not yet implemented")
