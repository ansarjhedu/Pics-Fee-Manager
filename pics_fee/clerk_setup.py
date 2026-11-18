"""Build a clerk setup file that already knows the principal's address."""

from __future__ import annotations

import ipaddress
import json
import re
import struct
import sys
from pathlib import Path

from pics_fee.constants import PORT
from pics_fee.errors import DeskError
from pics_fee.security import normalize_fingerprint

MAGIC = b"PICSCLERKSETUP1"
_USERNAME = re.compile(r"^[A-Za-z0-9._-]{3,64}$")


def bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1] / "dist" / "setup-stage"


def _existing(*candidates: Path) -> Path | None:
    for path in candidates:
        if path.is_file():
            return path
    return None


def stub_path() -> Path | None:
    root = Path(__file__).resolve().parents[1]
    return _existing(
        bundle_dir() / "clerk-setup.stub.exe",
        root / "installer" / "clerk-setup.stub.exe",
    )


def base_path() -> Path | None:
    folder = bundle_dir()
    return _existing(
        folder / "clerk-setup.base.exe",
        folder / "PICS Clerk Setup Base.exe",
    )


def clerk_connection(host: str, port: int, fingerprint: str, username: str = "") -> dict:
    try:
        address = ipaddress.ip_address((host or "").strip())
    except ValueError as exc:
        raise DeskError("Choose this computer's address on the college network.") from exc
    if not isinstance(address, ipaddress.IPv4Address) or address.is_loopback or address.is_unspecified or address.is_multicast:
        raise DeskError("Choose this computer's address on the college network.")
    number = int(port)
    if not 1 <= number <= 65535:
        raise DeskError("The connection port is not valid.")
    payload = {
        "host": str(address),
        "port": number,
        "fingerprint": normalize_fingerprint(fingerprint),
    }
    clerk = (username or "").strip()
    if _USERNAME.fullmatch(clerk):
        payload["username"] = clerk
    return payload


def pack_clerk_setup(dest: Path, stub: bytes, installer: bytes, config: dict) -> None:
    if len(stub) < 64 or len(installer) < 1000:
        raise DeskError("The clerk setup pieces on this computer are incomplete. Run the principal setup again.")
    payload = json.dumps(config, separators=(",", ":")).encode("utf-8")
    if not 2 <= len(payload) <= 100_000:
        raise DeskError("The clerk connection could not be saved into the setup file.")
    blob = stub + installer + payload + struct.pack("<Q", len(installer)) + struct.pack("<I", len(payload)) + MAGIC
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(blob)


def read_clerk_setup(blob: bytes) -> tuple[bytes, dict]:
    if not blob.endswith(MAGIC):
        raise DeskError("This setup file is incomplete.")
    end = len(blob) - len(MAGIC)
    if end < 12:
        raise DeskError("This setup file is incomplete.")
    config_len = struct.unpack_from("<I", blob, end - 4)[0]
    setup_len = struct.unpack_from("<Q", blob, end - 12)[0]
    config_pos = end - 12 - config_len
    setup_pos = config_pos - setup_len
    if config_len < 2 or setup_len < 1000 or setup_pos < 0:
        raise DeskError("This setup file is incomplete.")
    installer = blob[setup_pos : setup_pos + setup_len]
    config = json.loads(blob[config_pos : config_pos + config_len].decode("utf-8"))
    return installer, config


def write_clerk_setup(dest: Path, host: str, port: int, fingerprint: str, username: str = "") -> dict:
    stub = stub_path()
    installer = base_path()
    if stub is None or installer is None:
        raise DeskError(
            "The clerk setup pieces are installed with the principal's program. "
            "Run PICS Fee Desk Setup on this computer again, then save the clerk file."
        )
    config = clerk_connection(host, port, fingerprint, username)
    pack_clerk_setup(dest, stub.read_bytes(), installer.read_bytes(), config)
    return config
