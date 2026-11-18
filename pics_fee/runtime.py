from __future__ import annotations

import logging
import sys
import threading
import time
import traceback

from pics_fee.certs import ensure_certificate
from pics_fee.constants import PORT
from pics_fee.db import init_db
from pics_fee.paths import cert_path, data_dir, key_path

_started = False


def ensure_stdio() -> None:
    """A windowed app has no console. Uvicorn checks stderr.isatty() while starting."""
    if sys.stderr is not None and sys.stdout is not None:
        return
    log_path = data_dir() / "server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stream = open(log_path, "a", encoding="utf-8", buffering=1)
    if sys.stderr is None:
        sys.stderr = stream
    if sys.stdout is None:
        sys.stdout = stream


class ServerStartError(Exception):
    pass


def _up(fingerprint: str) -> bool:
    from pics_fee.client_api import Api, ApiError

    try:
        Api("127.0.0.1", PORT, fingerprint).request("GET", "/health", timeout=2)
        return True
    except (ApiError, OSError):
        return False


def ensure_server_running() -> str:
    global _started
    from pics_fee.machine import ensure_machine_role

    ensure_machine_role("principal")
    init_db()
    fingerprint = ensure_certificate()
    if _up(fingerprint):
        return fingerprint
    if not _started:
        _started = True
        _launch()
    for _ in range(40):
        if _up(fingerprint):
            return fingerprint
        time.sleep(0.25)
    raise ServerStartError(
        "The fee server did not start. If another program is using port 8765, close it and open PICS Fee again."
    )


def _launch() -> None:
    import uvicorn

    from pics_fee.server import create_app

    ensure_stdio()
    log_path = data_dir() / "server.log"
    logging.basicConfig(filename=log_path, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    config = uvicorn.Config(
        create_app(),
        host="0.0.0.0",
        port=PORT,
        ssl_certfile=str(cert_path()),
        ssl_keyfile=str(key_path()),
        log_level="warning",
        access_log=False,
        use_colors=False,
    )
    server = uvicorn.Server(config)

    def run() -> None:
        try:
            server.run()
        except Exception:
            logging.exception("The fee server stopped.")
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(traceback.format_exc())

    threading.Thread(target=run, name="pics-fee-server", daemon=True).start()
