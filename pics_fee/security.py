from __future__ import annotations

import base64
import ctypes
import hashlib
import hmac
import os
import re
import secrets
from ctypes import wintypes

from pics_fee.constants import MIN_PASSWORD, PASSWORD_ITERATIONS
from pics_fee.errors import DeskError


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return "pbkdf2$" + salt.hex() + "$" + digest.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
        if scheme != "pbkdf2":
            return False
        salt = bytes.fromhex(salt_hex)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def check_password_rules(password: str) -> None:
    if password is None or len(password) < MIN_PASSWORD:
        raise DeskError(f"Use a password of at least {MIN_PASSWORD} characters.")


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_fingerprint(value: str) -> str:
    hexed = re.sub(r"[^0-9a-fA-F]", "", value or "")
    if len(hexed) != 64:
        raise DeskError("The fingerprint should be the 64-character code from the principal's computer.")
    return hexed.lower()


def format_fingerprint(hexed: str) -> str:
    compact = re.sub(r"[^0-9a-fA-F]", "", hexed or "").lower()
    return " ".join(compact[i : i + 8] for i in range(0, len(compact), 8))


class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def seal_secret(text: str) -> str:
    if os.name != "nt":
        return "plain:" + text
    blob = _protect(text.encode("utf-8"))
    return "dpapi:" + base64.b64encode(blob).decode("ascii")


def unseal_secret(value: str) -> str:
    if not value:
        return ""
    if value.startswith("plain:"):
        return value[len("plain:") :]
    if value.startswith("dpapi:"):
        raw = base64.b64decode(value[len("dpapi:") :])
        return _unprotect(raw).decode("utf-8")
    return value


def _protect(data: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    in_buf = ctypes.create_string_buffer(data)
    in_blob = _BLOB(len(data), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_char)))
    out_blob = _BLOB()
    if not crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "PICS fee SMS key",
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise OSError("Could not protect the SMS key on this Windows account.")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _unprotect(data: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    in_buf = ctypes.create_string_buffer(data)
    in_blob = _BLOB(len(data), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_char)))
    out_blob = _BLOB()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise OSError("Could not read the SMS key on this Windows account.")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)
