"""
Pydantic Schemas and Enums for Phase 6 Network Sovereignty and Policy.
"""
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class NetworkProtocol(str, Enum):
    HTTP = "http"
    HTTPS = "https"
    TCP = "tcp"


class DestinationClass(str, Enum):
    LOOPBACK = "loopback"
    PRIVATE = "private"
    LINK_LOCAL = "link_local"
    PUBLIC = "public"
    MULTICAST = "multicast"
    UNSPECIFIED = "unspecified"
    UNKNOWN = "unknown"


class NetworkPolicyMode(str, Enum):
    STRICT = "strict"
    DEVELOPMENT = "development"


class PolicyDecision(str, Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"


class NetworkDestination(BaseModel):
    """Strongly typed destination allowlist entry."""
    host: str
    port: int = Field(ge=1, le=65535)
    protocol: NetworkProtocol = NetworkProtocol.HTTP
    purpose: str = ""
    enabled: bool = True

    model_config = ConfigDict(frozen=True)

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("Host cannot be empty")
        # Reject URLs with schemes or paths
        if "://" in v or "/" in v or "?" in v or "#" in v or "@" in v:
            raise ValueError(f"Host '{v}' must be a pure hostname or IP without scheme, path, query, or credentials")
        # Reject wildcard configurations in strict mode
        if v in {"0.0.0.0", "::", "0.0.0.0/0", "::/0", "*"}:
            raise ValueError(f"Wildcard host '{v}' is strictly prohibited in sovereign network destinations")
        return v


class NetworkEvent(BaseModel):
    """Schema for structured network audit events."""
    id: Optional[int] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    component: str
    method: Optional[str] = None
    requested_host: str
    resolved_ip: Optional[str] = None
    port: Optional[int] = None
    destination_class: DestinationClass
    policy_decision: PolicyDecision
    reason: str

    model_config = ConfigDict(from_attributes=True)


# Domain-specific exceptions
class NetworkPolicyViolation(Exception):
    """Raised when an outbound connection attempt violates the active network policy."""
    pass


class LocalServiceUnavailable(Exception):
    """Raised when a legitimate local service (e.g. Ollama) cannot be reached."""
    pass


class ModelAssetUnavailableError(Exception):
    """Raised when a required model/embedding asset is missing and auto-download is prohibited."""
    pass


class NetworkConfigurationError(Exception):
    """Raised when network policy configuration is invalid or dangerous."""
    pass
