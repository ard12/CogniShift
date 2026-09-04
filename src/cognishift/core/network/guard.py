"""
Sovereign HTTP Transport Guard & Approved Client Factory.
Intercepts all outbound HTTP/HTTPS communication, enforcing NetworkPolicy and logging audit events.
"""
import asyncio
from typing import Optional
import httpx
import logging

from cognishift.core.network.schemas import (
    PolicyDecision,
    NetworkPolicyViolation,
    NetworkPolicyMode,
    NetworkDestination,
)
from cognishift.core.network.policy import NetworkPolicy
from cognishift.core.network.events import log_network_event

logger = logging.getLogger(__name__)

# Global singleton policy instance
_global_policy: Optional[NetworkPolicy] = None


def get_active_network_policy() -> NetworkPolicy:
    """Returns the active global NetworkPolicy, initialized from application settings."""
    global _global_policy
    if _global_policy is None:
        from cognishift.app.config import settings
        mode = NetworkPolicyMode(getattr(settings, "network_policy_mode", "strict"))
        destinations = getattr(settings, "network_allowed_destinations", None)
        _global_policy = NetworkPolicy(mode=mode, allowed_destinations=destinations)
    return _global_policy


def set_active_network_policy(policy: NetworkPolicy):
    """Sets or overrides the active global NetworkPolicy (used in testing)."""
    global _global_policy
    _global_policy = policy


class SovereignAsyncTransport(httpx.AsyncBaseTransport):
    """
    Custom HTTP transport that intercepts and validates every outbound request
    against the active NetworkPolicy before any socket connection is attempted.
    """

    def __init__(
        self,
        policy: Optional[NetworkPolicy] = None,
        component: str = "core",
        underlying_transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self._policy = policy
        self.component = component
        self._underlying = underlying_transport or httpx.AsyncHTTPTransport()

    @property
    def policy(self) -> NetworkPolicy:
        return self._policy or get_active_network_policy()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        host = url.host
        port = url.port or (443 if url.scheme == "https" else 80)
        scheme = url.scheme
        method = request.method

        # 1. Deterministic evaluation
        decision, dest_class, resolved_ip, reason = self.policy.evaluate(
            host=host,
            port=port,
            scheme=scheme,
            component=self.component,
        )

        # 2. Structured audit logging (metadata only; zero secrets or bodies)
        try:
            await log_network_event(
                component=self.component,
                method=method,
                requested_host=host,
                resolved_ip=resolved_ip,
                port=port,
                destination_class=dest_class,
                policy_decision=decision,
                reason=reason,
            )
        except Exception as e:
            logger.warning(f"Could not persist network event to audit log: {e}")

        # 3. Enforcement
        if decision == PolicyDecision.BLOCKED:
            raise NetworkPolicyViolation(
                f"[NETWORK POLICY VIOLATION] Outbound {method} request to {host}:{port} ({dest_class.value}) "
                f"blocked by policy: {reason}"
            )

        # 4. Strict IP Pinning & DNS TOCTOU Protection:
        # Re-target request directly to the validated resolved IP address so the
        # underlying transport connects exclusively to the IP that passed policy evaluation.
        if resolved_ip and host != resolved_ip:
            original_host_header = request.headers.get("host") or (f"{host}:{port}" if port not in (80, 443) else host)
            request.url = request.url.copy_with(host=resolved_ip)
            request.headers["host"] = original_host_header

        response = await self._underlying.handle_async_request(request)

        # 5. Redirect validation: if server returns 3xx, intercept and validate redirect location
        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location")
            if location:
                redirect_url = httpx.URL(location)
                redir_host = redirect_url.host or host
                redir_port = redirect_url.port or (443 if redirect_url.scheme == "https" else 80)
                redir_scheme = redirect_url.scheme or scheme

                redir_decision, redir_class, redir_ip, redir_reason = self.policy.evaluate(
                    host=redir_host,
                    port=redir_port,
                    scheme=redir_scheme,
                    component=self.component,
                )

                try:
                    await log_network_event(
                        component=self.component,
                        method="REDIRECT",
                        requested_host=redir_host,
                        resolved_ip=redir_ip,
                        port=redir_port,
                        destination_class=redir_class,
                        policy_decision=redir_decision,
                        reason=f"Redirect check: {redir_reason}",
                    )
                except Exception:
                    pass

                if redir_decision == PolicyDecision.BLOCKED:
                    await response.aclose()
                    raise NetworkPolicyViolation(
                        f"[NETWORK POLICY VIOLATION] HTTP redirect from {host}:{port} to {redir_host}:{redir_port} "
                        f"({redir_class.value}) blocked by policy: {redir_reason}"
                    )

        return response

    async def aclose(self):
        if hasattr(self._underlying, "aclose"):
            await self._underlying.aclose()


class SovereignTransport(httpx.BaseTransport):
    """Synchronous version of Sovereign Transport."""

    def __init__(
        self,
        policy: Optional[NetworkPolicy] = None,
        component: str = "core",
        underlying_transport: Optional[httpx.BaseTransport] = None,
    ):
        self._policy = policy
        self.component = component
        self._underlying = underlying_transport or httpx.HTTPTransport()

    @property
    def policy(self) -> NetworkPolicy:
        return self._policy or get_active_network_policy()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        host = url.host
        port = url.port or (443 if url.scheme == "https" else 80)
        scheme = url.scheme
        method = request.method

        decision, dest_class, resolved_ip, reason = self.policy.evaluate(
            host=host,
            port=port,
            scheme=scheme,
            component=self.component,
        )

        if decision == PolicyDecision.BLOCKED:
            raise NetworkPolicyViolation(
                f"[NETWORK POLICY VIOLATION] Outbound {method} request to {host}:{port} ({dest_class.value}) "
                f"blocked by policy: {reason}"
            )

        # Strict IP Pinning & DNS TOCTOU Protection:
        if resolved_ip and host != resolved_ip:
            original_host_header = request.headers.get("host") or (f"{host}:{port}" if port not in (80, 443) else host)
            request.url = request.url.copy_with(host=resolved_ip)
            request.headers["host"] = original_host_header

        response = self._underlying.handle_request(request)

        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location")
            if location:
                redirect_url = httpx.URL(location)
                redir_host = redirect_url.host or host
                redir_port = redirect_url.port or (443 if redirect_url.scheme == "https" else 80)
                redir_scheme = redirect_url.scheme or scheme

                redir_decision, redir_class, redir_ip, redir_reason = self.policy.evaluate(
                    host=redir_host,
                    port=redir_port,
                    scheme=redir_scheme,
                    component=self.component,
                )

                if redir_decision == PolicyDecision.BLOCKED:
                    response.close()
                    raise NetworkPolicyViolation(
                        f"[NETWORK POLICY VIOLATION] HTTP redirect from {host}:{port} to {redir_host}:{redir_port} "
                        f"({redir_class.value}) blocked by policy: {redir_reason}"
                    )

        return response

    def close(self):
        if hasattr(self._underlying, "close"):
            self._underlying.close()


def get_sovereign_async_client(
    timeout: float = 120.0,
    follow_redirects: bool = False,
    component: str = "core",
    policy: Optional[NetworkPolicy] = None,
) -> httpx.AsyncClient:
    """
    Factory creating a secure httpx.AsyncClient with sovereign network policy enforcement.
    By default follow_redirects is False to avoid unvalidated redirect chains.
    """
    transport = SovereignAsyncTransport(policy=policy, component=component)
    return httpx.AsyncClient(
        transport=transport,
        timeout=timeout,
        follow_redirects=follow_redirects,
    )


def get_sovereign_client(
    timeout: float = 30.0,
    follow_redirects: bool = False,
    component: str = "core",
    policy: Optional[NetworkPolicy] = None,
) -> httpx.Client:
    """Factory creating a synchronous sovereign client."""
    transport = SovereignTransport(policy=policy, component=component)
    return httpx.Client(
        transport=transport,
        timeout=timeout,
        follow_redirects=follow_redirects,
    )
