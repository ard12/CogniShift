"""Local TLS certificate authority and server certificate generation for secure LAN deployment."""
import datetime
import ipaddress
import logging
from pathlib import Path
from typing import Optional, Tuple, List

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from cognishift.app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_SERVER_IPS = ["10.10.182.228", "127.0.0.1"]
DEFAULT_SERVER_HOSTNAMES = ["localhost"]


def get_default_cert_dir() -> Path:
    certs_dir = settings.data_dir / "certs"
    certs_dir.mkdir(parents=True, exist_ok=True)
    return certs_dir


def generate_ca(ca_cert_path: Path, ca_key_path: Path, common_name: str = "CogniShift Local Demo CA") -> Tuple[x509.Certificate, rsa.RSAPrivateKey]:
    """Generate a self-signed root CA certificate and private key."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    name = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "CogniShift Sovereign Systems"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    ca_key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    ca_cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    logger.info(f"Generated new Local Demo CA at {ca_cert_path}")
    return cert, key


def generate_server_cert(
    server_cert_path: Path,
    server_key_path: Path,
    ca_cert: x509.Certificate,
    ca_key: rsa.RSAPrivateKey,
    san_ips: Optional[List[str]] = None,
    san_hostnames: Optional[List[str]] = None,
) -> Tuple[x509.Certificate, rsa.RSAPrivateKey]:
    """Generate and sign a local server certificate valid for specified SANs."""
    ips = san_ips or DEFAULT_SERVER_IPS
    hostnames = san_hostnames or DEFAULT_SERVER_HOSTNAMES

    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server_name = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "CogniShift Sovereign Systems"),
        x509.NameAttribute(NameOID.COMMON_NAME, "CogniShift LAN Server"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)

    san_list: List[x509.GeneralName] = [x509.DNSName(h) for h in hostnames]
    for ip_str in ips:
        try:
            san_list.append(x509.IPAddress(ipaddress.ip_address(ip_str)))
        except ValueError:
            logger.warning(f"Invalid IP address for SAN: {ip_str}")

    cert = (
        x509.CertificateBuilder()
        .subject_name(server_name)
        .issuer_name(ca_cert.subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .add_extension(
            x509.SubjectAlternativeName(san_list),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    server_key_path.write_bytes(
        server_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    server_cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    logger.info(f"Generated new Local Server Certificate at {server_cert_path}")
    return cert, server_key


def ensure_local_tls_certificates(
    cert_dir: Optional[Path] = None,
    server_ips: Optional[List[str]] = None,
    server_hostnames: Optional[List[str]] = None,
) -> Tuple[Path, Path, Path]:
    """
    Ensure Root CA, server cert, and server key exist.
    Returns (ca_cert_path, server_cert_path, server_key_path).
    """
    target_dir = cert_dir or get_default_cert_dir()
    ca_cert_path = target_dir / "cognishift_demo_ca.crt"
    ca_key_path = target_dir / "cognishift_demo_ca.key"
    server_cert_path = target_dir / "server_cert.pem"
    server_key_path = target_dir / "server_key.pem"

    if ca_cert_path.exists() and ca_key_path.exists():
        ca_cert = x509.load_pem_x509_certificate(ca_cert_path.read_bytes())
        ca_key = serialization.load_pem_private_key(ca_key_path.read_bytes(), password=None)
    else:
        ca_cert, ca_key = generate_ca(ca_cert_path, ca_key_path)

    if not (server_cert_path.exists() and server_key_path.exists()):
        generate_server_cert(
            server_cert_path,
            server_key_path,
            ca_cert,
            ca_key,
            san_ips=server_ips,
            san_hostnames=server_hostnames,
        )

    return ca_cert_path, server_cert_path, server_key_path
