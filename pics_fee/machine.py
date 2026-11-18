from __future__ import annotations

import os
from pathlib import Path


class MachineRoleError(Exception):
    pass


def machine_role_path() -> Path:
    override = os.environ.get("PICS_DATA_DIR")
    if override:
        root = Path(override)
    else:
        root = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "PICS" / "FeeDesk"
    return root / "machine.role"


def _has_principal_account() -> bool:
    path = machine_role_path().with_name("fee.db")
    if not path.exists():
        return False
    import sqlite3

    connection = sqlite3.connect(path)
    try:
        row = connection.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()
    except sqlite3.Error:
        return False
    finally:
        connection.close()
    return bool(row and row[0])


def _clerk_connection_exists() -> bool:
    from pics_fee.client_api import load_clerk_config

    return load_clerk_config() is not None


def read_machine_role() -> str:
    path = machine_role_path()
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8-sig").strip().lower()
    if text in {"principal", "clerk"}:
        return text
    return ""


def _write(role: str) -> None:
    path = machine_role_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(role + "\n", encoding="utf-8")


def ensure_machine_role(expected: str) -> None:
    """Keep the role chosen for this computer.

    A later install cannot turn a clerk computer into the principal's computer,
    and it cannot turn the principal's computer into a clerk desk.
    """
    if expected not in {"principal", "clerk"}:
        raise MachineRoleError("This computer's role is not valid.")
    current = read_machine_role()
    if current == expected:
        return
    if current == "clerk" and expected == "principal":
        raise MachineRoleError(
            "This computer is a clerk desk. It connects to the principal's computer "
            "and cannot open or take over the fee records."
        )
    if current == "principal" and expected == "clerk":
        raise MachineRoleError(
            "This computer keeps the college fee records. It stays the principal's desk."
        )
    if expected == "principal" and _clerk_connection_exists() and not _has_principal_account():
        _write("clerk")
        raise MachineRoleError(
            "This computer is a clerk desk. It connects to the principal's computer "
            "and cannot open or take over the fee records."
        )
    if expected == "clerk" and _has_principal_account():
        _write("principal")
        raise MachineRoleError(
            "This computer keeps the college fee records. It stays the principal's desk."
        )
    _write(expected)
