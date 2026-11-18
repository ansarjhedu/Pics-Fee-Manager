import json
from pathlib import Path

import pytest

from pics_fee.clerk_setup import MAGIC, clerk_connection, pack_clerk_setup, read_clerk_setup
from pics_fee.errors import DeskError


def test_clerk_setup_file_carries_the_connection(tmp_path):
    config = clerk_connection("10.1.1.20", 8765, "ab" * 32, "amir")
    dest = tmp_path / "PICS Fee Desk - Amir.exe"
    pack_clerk_setup(dest, b"S" * 64, b"I" * 1000, config)
    installer, saved = read_clerk_setup(dest.read_bytes())
    assert installer == b"I" * 1000
    assert saved == {
        "host": "10.1.1.20",
        "port": 8765,
        "fingerprint": "ab" * 32,
        "username": "amir",
    }
    assert dest.read_bytes().endswith(MAGIC)


def test_clerk_setup_rejects_a_loopback_address():
    with pytest.raises(DeskError):
        clerk_connection("127.0.0.1", 8765, "ab" * 32, "amir")


def test_connection_file_keeps_the_clerk_username(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from pics_fee.client_api import load_clerk_config
    from pics_fee.paths import clerk_config_path

    path = clerk_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"host": "10.1.1.20", "port": 8765, "fingerprint": "ab" * 32, "username": "amir"}),
        encoding="utf-8",
    )
    saved = load_clerk_config()
    assert saved["username"] == "amir"
    assert saved["host"] == "10.1.1.20"


def test_stub_uses_the_same_marker_and_switches():
    text = Path("installer/ClerkSetupStub.cs").read_text(encoding="utf-8")
    assert "PICSCLERKSETUP1" in text
    assert "/HOST=" in text
    assert "/PORT=" in text
    assert "/FP=" in text
    assert "/CLERK=" in text
