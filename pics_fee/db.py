from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager

from pics_fee.constants import COLLEGE_NAME, PAYMENT_TEMPLATE, REMINDER_TEMPLATE, VOUCHER_PREFIX
from pics_fee.paths import db_path

_lock = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'clerk')),
    active INTEGER NOT NULL DEFAULT 1,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    machine TEXT,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    username TEXT,
    action TEXT NOT NULL,
    entity TEXT,
    entity_id INTEGER,
    detail TEXT,
    machine TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS class_sections (
    id INTEGER PRIMARY KEY,
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    name TEXT NOT NULL COLLATE NOCASE,
    UNIQUE (class_id, name)
);

CREATE TABLE IF NOT EXISTS academic_sessions (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fee_packages (
    id INTEGER PRIMARY KEY,
    class_id INTEGER NOT NULL REFERENCES classes(id),
    academic_session_id INTEGER NOT NULL REFERENCES academic_sessions(id),
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (class_id, academic_session_id, name)
);

CREATE TABLE IF NOT EXISTS fee_package_items (
    id INTEGER PRIMARY KEY,
    package_id INTEGER NOT NULL REFERENCES fee_packages(id) ON DELETE CASCADE,
    head_name TEXT NOT NULL,
    amount_paisa INTEGER NOT NULL CHECK (amount_paisa > 0),
    due_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY,
    admission_no TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    father_name TEXT NOT NULL,
    class_id INTEGER NOT NULL REFERENCES classes(id),
    section TEXT NOT NULL DEFAULT '',
    academic_session_id INTEGER NOT NULL REFERENCES academic_sessions(id),
    phone TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'left')),
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS student_charges (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    head_name TEXT NOT NULL,
    amount_paisa INTEGER NOT NULL CHECK (amount_paisa > 0),
    concession_paisa INTEGER NOT NULL DEFAULT 0 CHECK (concession_paisa >= 0),
    concession_reason TEXT,
    due_date TEXT NOT NULL,
    source_package_id INTEGER REFERENCES fee_packages(id),
    created_at TEXT NOT NULL,
    CHECK (concession_paisa <= amount_paisa)
);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY,
    clerk_id INTEGER NOT NULL REFERENCES users(id),
    submitted_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'closed')),
    counted_paisa INTEGER,
    note TEXT,
    closed_at TEXT
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id),
    amount_paisa INTEGER NOT NULL CHECK (amount_paisa > 0),
    voucher_no TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('unsubmitted', 'submitted', 'approved', 'rejected', 'cancelled')),
    submission_id INTEGER REFERENCES submissions(id),
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    approved_by INTEGER REFERENCES users(id),
    approved_at TEXT,
    reject_reason TEXT,
    rejected_by INTEGER REFERENCES users(id),
    rejected_at TEXT
);

CREATE TABLE IF NOT EXISTS adjustments (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id),
    amount_paisa INTEGER NOT NULL CHECK (amount_paisa != 0),
    reason TEXT NOT NULL,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sms_messages (
    id INTEGER PRIMARY KEY,
    student_id INTEGER REFERENCES students(id),
    payment_id INTEGER REFERENCES payments(id),
    phone TEXT NOT NULL,
    body TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('payment', 'reminder')),
    status TEXT NOT NULL CHECK (status IN ('queued', 'sent', 'failed')),
    provider_ref TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    sent_at TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS voucher_counters (
    year INTEGER PRIMARY KEY,
    last_number INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_payments_student ON payments(student_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_payments_submission ON payments(submission_id);
CREATE INDEX IF NOT EXISTS idx_charges_student ON student_charges(student_id);
CREATE INDEX IF NOT EXISTS idx_sms_status ON sms_messages(status);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
"""

DEFAULTS = {
    "college_name": COLLEGE_NAME,
    "voucher_prefix": VOUCHER_PREFIX,
    "sms_api_url": "",
    "sms_api_key": "",
    "sms_sender": "",
    "sms_test_mode": "1",
    "sms_template_payment": PAYMENT_TEMPLATE,
    "sms_template_reminder": REMINDER_TEMPLATE,
}


def connect(path=None) -> sqlite3.Connection:
    target = path or db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(path=None) -> None:
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        for key, value in DEFAULTS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        conn.commit()
    finally:
        conn.close()


@contextmanager
def transaction(path=None):
    _lock.acquire()
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
        _lock.release()


def setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is None:
        return default
    return row["value"]


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
