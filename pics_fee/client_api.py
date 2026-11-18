from __future__ import annotations

import hashlib
import http.client
import json
import socket
import ssl

from pics_fee.errors import DeskError
from pics_fee.security import normalize_fingerprint


class ApiError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, fingerprint: str, timeout: float = 30):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        super().__init__(host, port, context=context, timeout=timeout)
        self._fingerprint = fingerprint

    def connect(self):
        super().connect()
        der = self.sock.getpeercert(binary_form=True)
        digest = hashlib.sha256(der).hexdigest()
        if digest != self._fingerprint:
            try:
                self.sock.close()
            except OSError:
                pass
            raise ssl.SSLError("fingerprint mismatch")


class Api:
    def __init__(self, host: str, port: int, fingerprint: str):
        self.host = host.strip()
        self.port = int(port)
        self.fingerprint = normalize_fingerprint(fingerprint)
        self.token: str | None = None
        self.machine = socket.gethostname()

    def request(self, method: str, path: str, body=None, timeout: float = 30):
        status, raw = self._exchange(method, path, body, timeout)
        if status == 401:
            raise ApiError(401, _detail(raw) or "Please sign in again.")
        if status >= 400:
            raise ApiError(status, _detail(raw) or "The fee desk could not do that.")
        if not raw:
            return None
        return json.loads(raw.decode("utf-8"))

    def request_bytes(self, method: str, path: str, timeout: float = 60) -> bytes:
        status, raw = self._exchange(method, path, None, timeout)
        if status >= 400:
            raise ApiError(status, _detail(raw) or "The fee desk could not do that.")
        return raw

    def _exchange(self, method: str, path: str, body, timeout: float) -> tuple[int, bytes]:
        conn = PinnedHTTPSConnection(self.host, self.port, self.fingerprint, timeout=timeout)
        headers = {"Accept": "application/json", "X-Machine-Name": self.machine}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        try:
            conn.request(method, path, body=data, headers=headers)
            response = conn.getresponse()
            raw = response.read()
            status = response.status
        except ssl.SSLError as exc:
            raise ApiError(
                0,
                "The certificate does not match the fingerprint from the principal's computer.",
            ) from exc
        except OSError as exc:
            raise ApiError(
                0,
                "The principal's computer is not reachable. Check that it is turned on and the address is correct.",
            ) from exc
        finally:
            conn.close()
        return status, raw


def _detail(raw: bytes) -> str:
    if not raw:
        return ""
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ""
    detail = data.get("detail", "")
    if isinstance(detail, str):
        return detail
    return "Some of the entered details are missing or not valid."


def load_clerk_config() -> dict | None:
    from pics_fee.paths import clerk_config_path

    path = clerk_config_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not data.get("host") or not data.get("fingerprint"):
        return None
    return data


def save_clerk_config(host: str, fingerprint: str, port: int) -> None:
    from pics_fee.paths import clerk_config_path

    normalized = normalize_fingerprint(fingerprint)
    payload = {"host": host.strip(), "port": int(port), "fingerprint": normalized}
    clerk_config_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")
