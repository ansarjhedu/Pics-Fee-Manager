from __future__ import annotations

import datetime
import hashlib
import ipaddress
import socket

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pics_fee.constants import COLLEGE_NAME
from pics_fee.paths import cert_path, key_path
from pics_fee.security import format_fingerprint


def lan_ips() -> list[str]:
    found: list[str] = []

    def add(ip: str) -> None:
        if ip and not ip.startswith("127.") and ip not in found:
            found.append(ip)

    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 80))
            add(probe.getsockname()[0])
        finally:
            probe.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            add(info[4][0])
    except OSError:
        pass
    return found


def ensure_certificate() -> str:
    """Create a stable local certificate and return its SHA-256 fingerprint."""
    cert_file = cert_path()
    key_file = key_path()
    if cert_file.exists() and key_file.exists():
        return fingerprint_of(cert_file.read_bytes())

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, COLLEGE_NAME),
            x509.NameAttribute(NameOID.COMMON_NAME, "PICS Fee Principal"),
        ]
    )
    alt_names: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]
    for ip in lan_ips():
        try:
            alt_names.append(x509.IPAddress(ipaddress.IPv4Address(ip)))
        except ValueError:
            continue
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    key_file.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    der = cert.public_bytes(serialization.Encoding.DER)
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return hashlib.sha256(der).hexdigest()


def fingerprint_of(pem_bytes: bytes) -> str:
    cert = x509.load_pem_x509_certificate(pem_bytes)
    return hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()


def fingerprint_display() -> str:
    return format_fingerprint(ensure_certificate())
