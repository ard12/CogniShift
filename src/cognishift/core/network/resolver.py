"""
DNS Resolution, IP Classification and TOCTOU Protection.
Uses python's standard library ipaddress module.
"""
import ipaddress
import socket
from typing import List, Tuple, Union, Optional
import logging

from cognishift.core.network.schemas import DestinationClass

logger = logging.getLogger(__name__)


def parse_ip(ip_str: str) -> Union[ipaddress.IPv4Address, ipaddress.IPv6Address]:
    """Parse an IP string into an IPv4Address or IPv6Address, handling zone IDs."""
    # Strip optional IPv6 scope/zone id (e.g. fe80::1%eth0)
    clean_ip = ip_str.split("%")[0]
    return ipaddress.ip_address(clean_ip)


def classify_ip(ip_target: Union[str, ipaddress.IPv4Address, ipaddress.IPv6Address]) -> DestinationClass:
    """
    Classifies an IP address into loopback, private, link-local, public, multicast, or unspecified.
    Strictly uses Python ipaddress module attributes.
    """
    if isinstance(ip_target, str):
        try:
            ip_obj = parse_ip(ip_target)
        except ValueError:
            return DestinationClass.UNKNOWN
    else:
        ip_obj = ip_target

    if ip_obj.is_loopback:
        return DestinationClass.LOOPBACK
    if ip_obj.is_link_local:
        return DestinationClass.LINK_LOCAL
    if ip_obj.is_multicast:
        return DestinationClass.MULTICAST
    if ip_obj.is_unspecified:
        return DestinationClass.UNSPECIFIED
    if ip_obj.is_reserved:
        return DestinationClass.LINK_LOCAL
    if ip_obj.is_private:
        return DestinationClass.PRIVATE
    if ip_obj.is_global:
        return DestinationClass.PUBLIC

    return DestinationClass.UNKNOWN


def resolve_host(host: str, port: int) -> List[str]:
    """
    Resolves a hostname to a list of unique canonical IP strings.
    If host is already an IP, returns it directly without DNS lookup.
    """
    clean_host = host.strip("[]")
    try:
        # Check if already a literal IP
        parse_ip(clean_host)
        return [clean_host]
    except ValueError:
        pass

    # Resolve via socket.getaddrinfo
    try:
        addr_info = socket.getaddrinfo(clean_host, port, proto=socket.IPPROTO_TCP)
        resolved_ips = []
        for family, socktype, proto, canonname, sockaddr in addr_info:
            ip_addr = sockaddr[0]
            if ip_addr not in resolved_ips:
                resolved_ips.append(ip_addr)
        return resolved_ips
    except socket.gaierror as e:
        logger.warning(f"DNS resolution failed for {host}:{port} -> {e}")
        return []


def classify_destination(host: str, port: int) -> Tuple[DestinationClass, List[str], Optional[str]]:
    """
    Resolves destination and applies most-restrictive security classification.
    Returns (overall_classification, all_resolved_ips, primary_ip).
    
    DNS Rebinding Protection:
    If a hostname resolves to multiple IPs (e.g. 127.0.0.1 and 8.8.8.8), the entire destination
    is classified by the highest-risk address (PUBLIC), ensuring fail-closed rejection.
    """
    resolved_ips = resolve_host(host, port)
    if not resolved_ips:
        return DestinationClass.UNKNOWN, [], None

    classes = [classify_ip(ip) for ip in resolved_ips]

    # Priority of risk (highest risk wins):
    # If any is PUBLIC -> PUBLIC
    # If any is LINK_LOCAL -> LINK_LOCAL
    # If any is MULTICAST -> MULTICAST
    # If any is UNSPECIFIED -> UNSPECIFIED
    # If any is PRIVATE and others are LOOPBACK -> PRIVATE
    # Only if ALL are LOOPBACK -> LOOPBACK
    if DestinationClass.PUBLIC in classes:
        overall = DestinationClass.PUBLIC
    elif DestinationClass.LINK_LOCAL in classes:
        overall = DestinationClass.LINK_LOCAL
    elif DestinationClass.MULTICAST in classes:
        overall = DestinationClass.MULTICAST
    elif DestinationClass.UNSPECIFIED in classes:
        overall = DestinationClass.UNSPECIFIED
    elif DestinationClass.UNKNOWN in classes:
        overall = DestinationClass.UNKNOWN
    elif DestinationClass.PRIVATE in classes:
        overall = DestinationClass.PRIVATE
    elif all(c == DestinationClass.LOOPBACK for c in classes):
        overall = DestinationClass.LOOPBACK
    else:
        overall = DestinationClass.UNKNOWN

    primary_ip = resolved_ips[0]
    return overall, resolved_ips, primary_ip
