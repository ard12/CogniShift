"""Phase 6 Tier A: Deterministic Policy Unit Tests.

Verifies destination classification, strict allowlisting, loopback constraints,
private LAN blocking, link-local blocking, public blocking, DNS multi-IP rebinding
fail-closed logic, HTTP redirect interception, and development mode behavior.
"""

import socket
import pytest
from pydantic import ValidationError

from cognishift.core.network.schemas import (
    DestinationClass,
    NetworkDestination,
    NetworkPolicyMode,
    PolicyDecision,
    NetworkPolicyViolation,
    NetworkConfigurationError,
)
from cognishift.core.network.resolver import (
    classify_ip,
    classify_destination,
    resolve_host,
)
from cognishift.core.network.policy import NetworkPolicy, DEFAULT_STRICT_DESTINATIONS


# ==============================================================================
# 1. IP and Host Destination Classification Tests
# ==============================================================================

def test_classify_ip_ipv4_loopback():
    assert classify_ip("127.0.0.1") == DestinationClass.LOOPBACK
    assert classify_ip("127.0.0.2") == DestinationClass.LOOPBACK
    assert classify_ip("127.255.255.254") == DestinationClass.LOOPBACK


def test_classify_ip_ipv6_loopback():
    assert classify_ip("::1") == DestinationClass.LOOPBACK


def test_classify_ip_private_rfc1918():
    assert classify_ip("10.0.0.1") == DestinationClass.PRIVATE
    assert classify_ip("172.16.0.1") == DestinationClass.PRIVATE
    assert classify_ip("172.31.255.255") == DestinationClass.PRIVATE
    assert classify_ip("192.168.1.1") == DestinationClass.PRIVATE
    assert classify_ip("192.168.100.50") == DestinationClass.PRIVATE


def test_classify_ip_private_ipv6_ula():
    assert classify_ip("fc00::1") == DestinationClass.PRIVATE
    assert classify_ip("fd12:3456:789a::1") == DestinationClass.PRIVATE


def test_classify_ip_link_local():
    assert classify_ip("169.254.169.254") == DestinationClass.LINK_LOCAL
    assert classify_ip("169.254.1.1") == DestinationClass.LINK_LOCAL
    assert classify_ip("fe80::1") == DestinationClass.LINK_LOCAL


def test_classify_ip_public():
    assert classify_ip("8.8.8.8") == DestinationClass.PUBLIC
    assert classify_ip("1.1.1.1") == DestinationClass.PUBLIC
    assert classify_ip("93.184.216.34") == DestinationClass.PUBLIC
    assert classify_ip("2606:4700:4700::1111") == DestinationClass.PUBLIC


# ==============================================================================
# 2. Schema Validation & Rejection of Wildcards
# ==============================================================================

def test_network_destination_valid():
    dest = NetworkDestination(host="127.0.0.1", port=11434)
    assert dest.host == "127.0.0.1"
    assert dest.port == 11434


def test_network_destination_rejects_wildcards():
    with pytest.raises(ValidationError):
        NetworkDestination(host="0.0.0.0", port=8000)

    with pytest.raises(ValidationError):
        NetworkDestination(host="::", port=8000)

    with pytest.raises(ValidationError):
        NetworkDestination(host="*", port=8000)


def test_network_destination_rejects_invalid_ports():
    with pytest.raises(ValidationError):
        NetworkDestination(host="127.0.0.1", port=0)

    with pytest.raises(ValidationError):
        NetworkDestination(host="127.0.0.1", port=65536)


# ==============================================================================
# 3. Policy Decision Logic in Strict Mode
# ==============================================================================

def test_policy_allows_default_loopback_ollama():
    policy = NetworkPolicy(mode=NetworkPolicyMode.STRICT)
    decision, dest_class, ip, reason = policy.evaluate("127.0.0.1", 11434)
    assert decision == PolicyDecision.ALLOWED
    assert dest_class == DestinationClass.LOOPBACK

    decision_v6, dest_class_v6, _, _ = policy.evaluate("::1", 11434)
    assert decision_v6 == PolicyDecision.ALLOWED
    assert dest_class_v6 == DestinationClass.LOOPBACK

    decision_lh, dest_class_lh, _, _ = policy.evaluate("localhost", 11434)
    assert decision_lh == PolicyDecision.ALLOWED
    assert dest_class_lh == DestinationClass.LOOPBACK


def test_policy_allows_default_loopback_fastapi():
    policy = NetworkPolicy(mode=NetworkPolicyMode.STRICT)
    decision, dest_class, ip, reason = policy.evaluate("127.0.0.1", 8000)
    assert decision == PolicyDecision.ALLOWED

    decision_lh, _, _, _ = policy.evaluate("localhost", 8000)
    assert decision_lh == PolicyDecision.ALLOWED


def test_policy_blocks_unauthorized_loopback_port_in_strict():
    policy = NetworkPolicy(mode=NetworkPolicyMode.STRICT)
    decision, dest_class, ip, reason = policy.evaluate("127.0.0.1", 9999)
    assert decision == PolicyDecision.BLOCKED
    assert "allowlist" in reason.lower()


def test_policy_blocks_unauthorized_private_lan():
    policy = NetworkPolicy(mode=NetworkPolicyMode.STRICT)
    decision, dest_class, ip, reason = policy.evaluate("192.168.1.50", 8080)
    assert decision == PolicyDecision.BLOCKED
    assert dest_class == DestinationClass.PRIVATE


def test_policy_allows_explicitly_allowlisted_private_destination():
    policy = NetworkPolicy(
        mode=NetworkPolicyMode.STRICT,
        allowed_destinations=list(DEFAULT_STRICT_DESTINATIONS) + [
            NetworkDestination(host="192.168.1.50", port=8080, purpose="Internal SCADA Gateway")
        ],
    )
    decision, dest_class, ip, reason = policy.evaluate("192.168.1.50", 8080)
    assert decision == PolicyDecision.ALLOWED
    assert dest_class == DestinationClass.PRIVATE


def test_policy_blocks_link_local_metadata_unconditionally():
    policy = NetworkPolicy(mode=NetworkPolicyMode.STRICT)
    decision, dest_class, ip, reason = policy.evaluate("169.254.169.254", 80)
    assert decision == PolicyDecision.BLOCKED
    assert dest_class == DestinationClass.LINK_LOCAL


def test_policy_blocks_public_destinations():
    policy = NetworkPolicy(mode=NetworkPolicyMode.STRICT)
    decision, dest_class, ip, reason = policy.evaluate("8.8.8.8", 53)
    assert decision == PolicyDecision.BLOCKED
    assert dest_class == DestinationClass.PUBLIC

    decision_v6, dest_class_v6, _, _ = policy.evaluate("2606:4700:4700::1111", 443)
    assert decision_v6 == PolicyDecision.BLOCKED
    assert dest_class_v6 == DestinationClass.PUBLIC


# ==============================================================================
# 4. DNS Multi-IP Rebinding & Fail-Closed Logic
# ==============================================================================

def test_dns_rebinding_fail_closed_if_one_ip_is_public(monkeypatch):
    """If a hostname resolves to multiple IPs, and ANY is public/un-allowlisted, fail closed."""
    policy = NetworkPolicy(mode=NetworkPolicyMode.STRICT)

    def mock_getaddrinfo(host, port, *args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

    decision, dest_class, ip, reason = policy.evaluate("rebind-attack.local", 11434)
    assert decision == PolicyDecision.BLOCKED
    assert dest_class == DestinationClass.PUBLIC


def test_dns_unresolvable_fails_closed(monkeypatch):
    policy = NetworkPolicy(mode=NetworkPolicyMode.STRICT)

    def mock_getaddrinfo_fail(host, port, *args, **kwargs):
        raise socket.gaierror(-2, "Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo_fail)

    decision, dest_class, ip, reason = policy.evaluate("nonexistent.domain.xyz", 80)
    assert decision == PolicyDecision.BLOCKED
    assert "could not be resolved" in reason.lower() or "dns" in reason.lower()


# ==============================================================================
# 5. Development Mode Logging & Non-Blocking Behavior
# ==============================================================================

def test_development_mode_allows_with_warning():
    policy = NetworkPolicy(mode=NetworkPolicyMode.DEVELOPMENT)
    decision, dest_class, ip, reason = policy.evaluate("8.8.8.8", 443)
    assert decision == PolicyDecision.ALLOWED
    assert "dev mode" in reason.lower()
