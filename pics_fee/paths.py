from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    """Folder that holds the database, certificate, and backups.

    The principal's computer uses Program Data so the records stay on that
    machine. If that folder cannot be created, the app uses the current
    Windows user's local data folder instead.
    """
    override = os.environ.get("PICS_DATA_DIR")
    if override:
        path = Path(override)
        path.mkdir(parents=True, exist_ok=True)
        return path

    program = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "PICS" / "FeeDesk"
    try:
        program.mkdir(parents=True, exist_ok=True)
        probe = program / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return program
    except OSError:
        local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        path = local / "PICS" / "FeeDesk"
        path.mkdir(parents=True, exist_ok=True)
        return path


def db_path() -> Path:
    return data_dir() / "fee.db"


def cert_path() -> Path:
    return data_dir() / "cert.pem"


def key_path() -> Path:
    return data_dir() / "key.pem"


def backup_dir() -> Path:
    path = data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sms_log_path() -> Path:
    return data_dir() / "sms-test.log"


def clerk_config_path() -> Path:
    root = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    path = root / "PICS" / "FeeDesk"
    path.mkdir(parents=True, exist_ok=True)
    return path / "connection.json"
