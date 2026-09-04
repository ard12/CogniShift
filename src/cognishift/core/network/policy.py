"""
Network Policy Evaluation Engine for CogniShift.
Enforces strict sovereignty policies, loopback allowlists, and RFC1918 private LAN isolation.
"""
from typing import List, Optional, Tuple, Set
import logging

from cognishift.core.network.schemas import (
    NetworkPolicyMode,
    PolicyDecision,
    DestinationClass,
    NetworkDestination,
    NetworkProtocol,
    NetworkConfigurationError,
)
from cognishift.core.network.resolver import classify_destination

logger = logging.getLogger(__name__)

DEFAULT_STRICT_DESTINATIONS = [
    NetworkDestination(
        host="127.0.0.1",
        port=11434,
        protocol=NetworkProtocol.HTTP,
        purpose="Ollama local LLM/VLM inference daemon",
        enabled=True
    ),
    NetworkDestination(
        host="::1",
        port=11434,
        protocol=NetworkProtocol.HTTP,
        purpose="Ollama local IPv6 loopback",
        enabled=True
    ),
    NetworkDestination(
        host="localhost",
        port=11434,
        protocol=NetworkProtocol.HTTP,
        purpose="Ollama local hostname alias",
        enabled=True
    ),
    NetworkDestination(
        host="127.0.0.1",
        port=8000,
        protocol=NetworkProtocol.HTTP,
        purpose="CogniShift local application server",
        enabled=True
    ),
    NetworkDestination(
        host="::1",
        port=8000,
        protocol=NetworkProtocol.HTTP,
        purpose="CogniShift local application IPv6 server",
        enabled=True
    ),
    NetworkDestination(
        host="localhost",
        port=8000,
        protocol=NetworkProtocol.HTTP,
        purpose="CogniShift local hostname alias",
        enabled=True
    ),
]


class NetworkPolicy:
    """
    Central deterministic network authorization policy.
    Evaluates every outbound connection attempt against the active mode and allowlist.
    """

    def __init__(
        self,
        mode: NetworkPolicyMode = NetworkPolicyMode.STRICT,
        allowed_destinations: Optional[List[NetworkDestination]] = None,
    ):
        self.mode = mode
        self.allowed_destinations = allowed_destinations or list(DEFAULT_STRICT_DESTINATIONS)
        self._validate_configuration()

    def _validate_configuration(self):
        """Rejects dangerous configurations such as wildcard allowlists."""
        for dest in self.allowed_destinations:
            if dest.host in {"0.0.0.0", "::", "*", "0.0.0.0/0", "::/0"}:
                raise NetworkConfigurationError(
                    f"Dangerous wildcard destination '{dest.host}' rejected in network configuration."
                )

    def evaluate(
        self,
        host: str,
        port: int,
        scheme: str = "http",
        component: str = "core"
    ) -> Tuple[PolicyDecision, DestinationClass, Optional[str], str]:
        """
        Evaluates a target destination.
        Returns: (decision, destination_class, resolved_primary_ip, reason)
        """
        dest_class, resolved_ips, primary_ip = classify_destination(host, port)

        if dest_class == DestinationClass.UNKNOWN:
            return (
                PolicyDecision.BLOCKED,
                dest_class,
                None,
                f"Destination {host}:{port} could not be resolved or is an invalid address."
            )

        # 1. Link-local / metadata addresses are unconditionally forbidden
        if dest_class == DestinationClass.LINK_LOCAL:
            return (
                PolicyDecision.BLOCKED,
                dest_class,
                primary_ip,
                f"Link-local and cloud metadata destination {host}:{port} ({primary_ip}) is strictly forbidden."
            )

        # 2. Multicast and unspecified addresses are unconditionally forbidden
        if dest_class in {DestinationClass.MULTICAST, DestinationClass.UNSPECIFIED}:
            return (
                PolicyDecision.BLOCKED,
                dest_class,
                primary_ip,
                f"Multicast/unspecified destination {host}:{port} is forbidden."
            )

        # 3. Public internet addresses
        if dest_class == DestinationClass.PUBLIC:
            if self.mode == NetworkPolicyMode.STRICT:
                return (
                    PolicyDecision.BLOCKED,
                    dest_class,
                    primary_ip,
                    f"Public internet egress to {host}:{port} ({primary_ip}) is strictly forbidden in sovereign mode."
                )
            else:
                return (
                    PolicyDecision.ALLOWED,
                    dest_class,
                    primary_ip,
                    f"[DEV MODE WARNING] Public egress to {host}:{port} allowed for development only."
                )

        # 4. Loopback addresses
        if dest_class == DestinationClass.LOOPBACK:
            # Check against allowed destinations
            allowed = False
            for rule in self.allowed_destinations:
                if not rule.enabled:
                    continue
                if rule.port == port:
                    rule_host = rule.host.strip("[]").lower()
                    query_host = host.strip("[]").lower()
                    p_ip = (primary_ip or "").strip("[]").lower()
                    if rule_host in {query_host, p_ip} or (
                        rule_host in {"127.0.0.1", "::1", "localhost"} and p_ip in {"127.0.0.1", "::1"}
                    ):
                        allowed = True
                        break

            if allowed:
                return (
                    PolicyDecision.ALLOWED,
                    dest_class,
                    primary_ip,
                    f"Explicitly permitted local service at {host}:{port}."
                )
            else:
                if self.mode == NetworkPolicyMode.STRICT:
                    return (
                        PolicyDecision.BLOCKED,
                        dest_class,
                        primary_ip,
                        f"Loopback destination {host}:{port} is not in the approved services allowlist."
                    )
                else:
                    return (
                        PolicyDecision.ALLOWED,
                        dest_class,
                        primary_ip,
                        f"[DEV MODE] Unlisted loopback port {port} allowed in development mode."
                    )

        # 5. Private LAN addresses (RFC 1918 / ULA)
        if dest_class == DestinationClass.PRIVATE:
            allowed = False
            for rule in self.allowed_destinations:
                if not rule.enabled:
                    continue
                if rule.port == port:
                    rule_host = rule.host.strip("[]").lower()
                    query_host = host.strip("[]").lower()
                    p_ip = (primary_ip or "").strip("[]").lower()
                    if rule_host in {query_host, p_ip}:
                        allowed = True
                        break

            if allowed:
                return (
                    PolicyDecision.ALLOWED,
                    dest_class,
                    primary_ip,
                    f"Explicitly allowlisted on-premise private LAN service at {host}:{port}."
                )
            else:
                if self.mode == NetworkPolicyMode.STRICT:
                    return (
                        PolicyDecision.BLOCKED,
                        dest_class,
                        primary_ip,
                        f"Private LAN destination {host}:{port} ({primary_ip}) is not authorized in strict mode."
                    )
                else:
                    return (
                        PolicyDecision.ALLOWED,
                        dest_class,
                        primary_ip,
                        f"[DEV MODE WARNING] Unlisted private LAN target {host}:{port} allowed in development mode."
                    )

        return (
            PolicyDecision.BLOCKED,
            DestinationClass.UNKNOWN,
            primary_ip,
            f"Unrecognized destination class for {host}:{port}."
        )
