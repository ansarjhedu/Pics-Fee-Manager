from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from pics_fee.audit import audit, now_iso
from pics_fee.constants import COLLEGE_NAME, LOCK_AFTER, LOCK_MINUTES, SESSION_HOURS, TEMPLATE_FIELDS
from pics_fee.context import current_machine
from pics_fee.db import set_setting, setting
from pics_fee.errors import DeskError
from pics_fee.phones import normalize_phone, to_sms_phone
from pics_fee.security import (
    check_password_rules,
    hash_password,
    hash_token,
    new_token,
    seal_secret,
    verify_password,
)
from pics_fee.textfmt import format_date, format_rs, parse_counted, parse_rupees

WAITING = ("unsubmitted", "submitted")
MATCH_STATUSES = ("submitted", "approved")


def parse_date(value: str) -> str:
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date().isoformat()
    except (TypeError, ValueError):
        raise DeskError("Enter the date as YYYY-MM-DD.") from None


def _clean(value: str, label: str, limit: int = 80) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise DeskError(f"Enter the {label}.")
    if len(text) > limit:
        raise DeskError(f"The {label} is too long.")
    return text


def _admin(actor) -> None:
    if not actor or actor.get("role") != "admin":
        raise DeskError("Only the principal can do this.")


def _clerk(actor) -> None:
    if not actor or actor.get("role") != "clerk":
        raise DeskError("Only a clerk can record cash.")


def _staff(actor) -> None:
    if not actor or actor.get("role") not in ("admin", "clerk"):
        raise DeskError("Please sign in again.")


def college_name(conn) -> str:
    return setting(conn, "college_name", COLLEGE_NAME) or COLLEGE_NAME


def is_initialized(conn) -> bool:
    return conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"] > 0


def public_user(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "role": row["role"],
        "active": bool(row["active"]),
    }


def _user_by_name(conn, username: str):
    return conn.execute(
        "SELECT * FROM users WHERE username = ? COLLATE NOCASE",
        (username.strip(),),
    ).fetchone()


def create_initial_admin(conn, username: str, password: str, display_name: str) -> dict:
    if is_initialized(conn):
        raise DeskError("The principal account already exists.")
    user_id = _insert_user(conn, username, display_name, password, "admin")
    user = public_user(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())
    audit(conn, user, "create_admin", f"Principal account created for {user['display_name']}", "user", user_id, current_machine())
    return user


def create_clerk(conn, actor, username: str, password: str, display_name: str) -> dict:
    _admin(actor)
    user_id = _insert_user(conn, username, display_name, password, "clerk")
    user = public_user(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())
    audit(conn, actor, "create_clerk", f"Clerk account created for {user['display_name']}", "user", user_id, current_machine())
    return user


def _insert_user(conn, username: str, display_name: str, password: str, role: str) -> int:
    check_password_rules(password)
    name = username.strip()
    if len(name) < 3 or any(ch.isspace() for ch in name):
        raise DeskError("Use a username of at least 3 characters, without spaces.")
    display = _clean(display_name, "name", 80)
    try:
        cursor = conn.execute(
            """
            INSERT INTO users (username, display_name, password_hash, role, active, failed_attempts, created_at)
            VALUES (?, ?, ?, ?, 1, 0, ?)
            """,
            (name, display, hash_password(password), role, now_iso()),
        )
    except sqlite3.IntegrityError:
        raise DeskError("That username is already in use.") from None
    return int(cursor.lastrowid)


def authenticate(conn, username: str, password: str) -> dict:
    row = _user_by_name(conn, username or "")
    if row is None:
        audit(conn, None, "login_failed", "Sign-in failed for an unknown username.", machine=current_machine())
        conn.commit()
        raise DeskError("Username or password is not correct.")
    if row["locked_until"] and row["locked_until"] > now_iso():
        raise DeskError("This account is paused for a few minutes after several wrong passwords.")
    if not verify_password(password or "", row["password_hash"]):
        attempts = int(row["failed_attempts"]) + 1
        locked = None
        if attempts >= LOCK_AFTER:
            locked = (datetime.now() + timedelta(minutes=LOCK_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
            attempts = 0
        conn.execute(
            "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
            (attempts, locked, row["id"]),
        )
        audit(conn, public_user(row), "login_failed", f"Wrong password for {row['username']}.", "user", row["id"], current_machine())
        conn.commit()
        raise DeskError("Username or password is not correct.")
    if not row["active"]:
        raise DeskError("This account is turned off. Ask the principal.")
    conn.execute("UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?", (row["id"],))
    user = public_user(row)
    audit(conn, user, "login", f"{user['display_name']} signed in.", "user", user["id"], current_machine())
    return user


def open_session(conn, user: dict) -> str:
    token = new_token()
    expires = (datetime.now() + timedelta(hours=SESSION_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, machine, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
        (hash_token(token), user["id"], current_machine(), expires, now_iso()),
    )
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now_iso(),))
    return token


def user_from_token(conn, token: str) -> dict | None:
    if not token:
        return None
    row = conn.execute(
        """
        SELECT u.*, s.expires_at, s.id AS session_id
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = ?
        """,
        (hash_token(token),),
    ).fetchone()
    if row is None:
        return None
    if row["expires_at"] < now_iso() or not row["active"]:
        conn.execute("DELETE FROM sessions WHERE id = ?", (row["session_id"],))
        return None
    return public_user(row)


def logout(conn, token: str, actor) -> None:
    if token:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))
    if actor:
        audit(conn, actor, "logout", f"{actor['display_name']} signed out.", "user", actor["id"], current_machine())


def list_clerks(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM users WHERE role = 'clerk' ORDER BY display_name COLLATE NOCASE"
    ).fetchall()
    return [public_user(row) for row in rows]


def reset_clerk_password(conn, actor, user_id: int, password: str) -> None:
    _admin(actor)
    row = conn.execute("SELECT * FROM users WHERE id = ? AND role = 'clerk'", (user_id,)).fetchone()
    if row is None:
        raise DeskError("That clerk account was not found.")
    check_password_rules(password)
    conn.execute(
        "UPDATE users SET password_hash = ?, failed_attempts = 0, locked_until = NULL WHERE id = ?",
        (hash_password(password), user_id),
    )
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    audit(conn, actor, "reset_password", f"Password reset for {row['display_name']}.", "user", user_id, current_machine())


def set_clerk_active(conn, actor, user_id: int, active: bool) -> dict:
    _admin(actor)
    row = conn.execute("SELECT * FROM users WHERE id = ? AND role = 'clerk'", (user_id,)).fetchone()
    if row is None:
        raise DeskError("That clerk account was not found.")
    conn.execute("UPDATE users SET active = ? WHERE id = ?", (1 if active else 0, user_id))
    if not active:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    state = "turned on" if active else "turned off"
    audit(conn, actor, "set_clerk_active", f"{row['display_name']} was {state}.", "user", user_id, current_machine())
    updated = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return public_user(updated)


def reset_admin_password(conn, username: str, password: str) -> None:
    check_password_rules(password)
    row = _user_by_name(conn, username or "")
    if row is None or row["role"] != "admin":
        raise DeskError("That principal account was not found on this computer.")
    conn.execute(
        "UPDATE users SET password_hash = ?, failed_attempts = 0, locked_until = NULL WHERE id = ?",
        (hash_password(password), row["id"]),
    )
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (row["id"],))
    audit(
        conn,
        None,
        "reset_admin_password",
        f"Principal password reset on this computer for {row['username']}.",
        "user",
        row["id"],
        current_machine(),
    )


def list_audit(conn, limit: int = 200, username: str = "") -> list[dict]:
    sql = "SELECT * FROM audit_log"
    params: list = []
    if username.strip():
        sql += " WHERE username = ?"
        params.append(username.strip())
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(max(1, min(int(limit), 500)))
    rows = conn.execute(sql, params).fetchall()
    result = []
    for row in rows:
        summary = row["action"]
        if row["detail"]:
            try:
                import json

                summary = json.loads(row["detail"]).get("summary") or summary
            except json.JSONDecodeError:
                summary = row["detail"]
        result.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "username": row["username"] or "",
                "action": row["action"],
                "summary": summary,
                "machine": row["machine"] or "",
            }
        )
    return result


def add_class(conn, actor, name: str) -> dict:
    _admin(actor)
    clean = _clean(name, "class name", 60)
    try:
        cursor = conn.execute("INSERT INTO classes (name, created_at) VALUES (?, ?)", (clean, now_iso()))
    except sqlite3.IntegrityError:
        raise DeskError("That class is already in the list.") from None
    audit(conn, actor, "create_class", f"Class added: {clean}.", "class", cursor.lastrowid, current_machine())
    return {"id": cursor.lastrowid, "name": clean}


def list_classes(conn) -> list[dict]:
    return [dict(row) for row in conn.execute("SELECT id, name FROM classes ORDER BY name COLLATE NOCASE")]


def class_board(conn, session_id: int | None = None, status: str = "active") -> list[dict]:
    classes = list_classes(conn)
    sql = "SELECT class_id, COALESCE(section, '') AS section, COUNT(*) AS n FROM students WHERE 1 = 1"
    params: list = []
    if status and status != "all":
        sql += " AND status = ?"
        params.append(status)
    if session_id:
        sql += " AND academic_session_id = ?"
        params.append(session_id)
    sql += " GROUP BY class_id, section"
    grouped: dict[int, dict[str, int]] = {}
    for row in conn.execute(sql, params):
        grouped.setdefault(row["class_id"], {})[row["section"]] = row["n"]
    defined: dict[int, list[dict]] = {}
    for row in conn.execute("SELECT id, class_id, name FROM class_sections ORDER BY name COLLATE NOCASE"):
        defined.setdefault(row["class_id"], []).append({"id": row["id"], "name": row["name"]})
    board = []
    for klass in classes:
        counts = grouped.get(klass["id"], {})
        sections = []
        seen = set()
        for item in defined.get(klass["id"], []):
            sections.append({"id": item["id"], "name": item["name"], "students": counts.get(item["name"], 0)})
            seen.add(item["name"].casefold())
        for section, count in sorted(counts.items(), key=lambda pair: pair[0].casefold()):
            if section.casefold() not in seen:
                sections.append({"id": None, "name": section, "students": count})
        board.append(
            {
                "id": klass["id"],
                "name": klass["name"],
                "students": sum(counts.values()),
                "sections": sections,
            }
        )
    return board


def add_section(conn, actor, class_id: int, name: str) -> dict:
    _admin(actor)
    clean = _clean(name, "section", 20)
    if conn.execute("SELECT 1 FROM classes WHERE id = ?", (class_id,)).fetchone() is None:
        raise DeskError("That class was not found.")
    try:
        cursor = conn.execute(
            "INSERT INTO class_sections (class_id, name) VALUES (?, ?)",
            (class_id, clean),
        )
    except sqlite3.IntegrityError:
        raise DeskError("That section is already on this class.") from None
    audit(conn, actor, "create_section", f"Section {clean} added.", "class", class_id, current_machine())
    return {"id": cursor.lastrowid, "class_id": class_id, "name": clean}


def delete_section(conn, actor, section_id: int) -> None:
    _admin(actor)
    row = conn.execute("SELECT * FROM class_sections WHERE id = ?", (section_id,)).fetchone()
    if row is None:
        raise DeskError("That section was not found.")
    used = conn.execute(
        "SELECT COUNT(*) AS c FROM students WHERE class_id = ? AND section = ?",
        (row["class_id"], row["name"]),
    ).fetchone()["c"]
    if used:
        raise DeskError("Students are already in this section, so it stays on the class.")
    conn.execute("DELETE FROM class_sections WHERE id = ?", (section_id,))
    audit(conn, actor, "delete_section", f"Section {row['name']} removed.", "class", row["class_id"], current_machine())


def delete_class(conn, actor, class_id: int) -> None:
    _admin(actor)
    row = conn.execute("SELECT * FROM classes WHERE id = ?", (class_id,)).fetchone()
    if row is None:
        raise DeskError("That class was not found.")
    used = conn.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM students WHERE class_id = ?) +
            (SELECT COUNT(*) FROM fee_packages WHERE class_id = ?) AS c
        """,
        (class_id, class_id),
    ).fetchone()["c"]
    if used:
        raise DeskError("That class is in use, so it stays on record.")
    conn.execute("DELETE FROM classes WHERE id = ?", (class_id,))
    audit(conn, actor, "delete_class", f"Class removed: {row['name']}.", "class", class_id, current_machine())


def add_session(conn, actor, name: str) -> dict:
    _admin(actor)
    clean = _clean(name, "session name", 40)
    try:
        cursor = conn.execute(
            "INSERT INTO academic_sessions (name, created_at) VALUES (?, ?)",
            (clean, now_iso()),
        )
    except sqlite3.IntegrityError:
        raise DeskError("That session is already in the list.") from None
    audit(conn, actor, "create_session", f"Session added: {clean}.", "session", cursor.lastrowid, current_machine())
    return {"id": cursor.lastrowid, "name": clean}


def list_sessions(conn) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute("SELECT id, name FROM academic_sessions ORDER BY name COLLATE NOCASE")
    ]


def delete_session(conn, actor, session_id: int) -> None:
    _admin(actor)
    row = conn.execute("SELECT * FROM academic_sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        raise DeskError("That session was not found.")
    used = conn.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM students WHERE academic_session_id = ?) +
            (SELECT COUNT(*) FROM fee_packages WHERE academic_session_id = ?) AS c
        """,
        (session_id, session_id),
    ).fetchone()["c"]
    if used:
        raise DeskError("That session is in use, so it stays on record.")
    conn.execute("DELETE FROM academic_sessions WHERE id = ?", (session_id,))
    audit(conn, actor, "delete_session", f"Session removed: {row['name']}.", "session", session_id, current_machine())


def _clean_items(items: list[dict]) -> list[dict]:
    if not items:
        raise DeskError("Add at least one fee head.")
    cleaned = []
    for item in items:
        head = _clean(item.get("head_name"), "fee head name", 60)
        amount = parse_rupees(item.get("amount_rupees"))
        due = parse_date(item.get("due_date"))
        cleaned.append({"head_name": head, "amount_paisa": amount, "due_date": due})
    return cleaned


def _require_class(conn, class_id: int):
    row = conn.execute("SELECT * FROM classes WHERE id = ?", (class_id,)).fetchone()
    if row is None:
        raise DeskError("Choose a class.")
    return row


def _require_session(conn, session_id: int):
    row = conn.execute("SELECT * FROM academic_sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        raise DeskError("Choose a session.")
    return row


def create_package(conn, actor, name: str, class_id: int, session_id: int, items: list[dict]) -> dict:
    _admin(actor)
    clean = _clean(name, "package name", 80)
    _require_class(conn, class_id)
    _require_session(conn, session_id)
    cleaned = _clean_items(items)
    try:
        cursor = conn.execute(
            """
            INSERT INTO fee_packages (class_id, academic_session_id, name, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (class_id, session_id, clean, now_iso()),
        )
    except sqlite3.IntegrityError:
        raise DeskError("That class and session already have a package with this name.") from None
    package_id = int(cursor.lastrowid)
    _replace_items(conn, package_id, cleaned)
    audit(conn, actor, "create_package", f"Fee package added: {clean}.", "package", package_id, current_machine())
    return get_package(conn, package_id)


def update_package(conn, actor, package_id: int, name: str, class_id: int, session_id: int, items: list[dict]) -> dict:
    _admin(actor)
    current = conn.execute("SELECT * FROM fee_packages WHERE id = ?", (package_id,)).fetchone()
    if current is None:
        raise DeskError("That fee package was not found.")
    clean = _clean(name, "package name", 80)
    _require_class(conn, class_id)
    _require_session(conn, session_id)
    cleaned = _clean_items(items)
    try:
        conn.execute(
            "UPDATE fee_packages SET name = ?, class_id = ?, academic_session_id = ? WHERE id = ?",
            (clean, class_id, session_id, package_id),
        )
    except sqlite3.IntegrityError:
        raise DeskError("That class and session already have a package with this name.") from None
    _replace_items(conn, package_id, cleaned)
    audit(
        conn,
        actor,
        "update_package",
        f"Fee package updated: {clean}. Students who already have it are unchanged.",
        "package",
        package_id,
        current_machine(),
    )
    return get_package(conn, package_id)


def _replace_items(conn, package_id: int, items: list[dict]) -> None:
    conn.execute("DELETE FROM fee_package_items WHERE package_id = ?", (package_id,))
    for item in items:
        conn.execute(
            """
            INSERT INTO fee_package_items (package_id, head_name, amount_paisa, due_date)
            VALUES (?, ?, ?, ?)
            """,
            (package_id, item["head_name"], item["amount_paisa"], item["due_date"]),
        )


def delete_package(conn, actor, package_id: int) -> None:
    _admin(actor)
    row = conn.execute("SELECT * FROM fee_packages WHERE id = ?", (package_id,)).fetchone()
    if row is None:
        raise DeskError("That fee package was not found.")
    used = conn.execute(
        "SELECT COUNT(*) AS c FROM student_charges WHERE source_package_id = ?",
        (package_id,),
    ).fetchone()["c"]
    if used:
        raise DeskError("Students already have this package, so it stays on record.")
    conn.execute("DELETE FROM fee_packages WHERE id = ?", (package_id,))
    audit(conn, actor, "delete_package", f"Fee package removed: {row['name']}.", "package", package_id, current_machine())


def list_packages(conn) -> list[dict]:
    packages = conn.execute(
        """
        SELECT p.*, c.name AS class_name, s.name AS session_name
        FROM fee_packages p
        JOIN classes c ON c.id = p.class_id
        JOIN academic_sessions s ON s.id = p.academic_session_id
        ORDER BY s.name, c.name, p.name
        """
    ).fetchall()
    items = conn.execute(
        "SELECT * FROM fee_package_items ORDER BY due_date, id"
    ).fetchall()
    grouped: dict[int, list] = {}
    for item in items:
        grouped.setdefault(item["package_id"], []).append(
            {
                "id": item["id"],
                "head_name": item["head_name"],
                "amount_paisa": item["amount_paisa"],
                "due_date": item["due_date"],
            }
        )
    result = []
    for package in packages:
        result.append(
            {
                "id": package["id"],
                "name": package["name"],
                "class_id": package["class_id"],
                "academic_session_id": package["academic_session_id"],
                "class_name": package["class_name"],
                "session_name": package["session_name"],
                "items": grouped.get(package["id"], []),
            }
        )
    return result


def get_package(conn, package_id: int) -> dict:
    for package in list_packages(conn):
        if package["id"] == package_id:
            return package
    raise DeskError("That fee package was not found.")


def _require_student(conn, student_id: int):
    row = conn.execute(
        """
        SELECT s.*, c.name AS class_name, a.name AS session_name
        FROM students s
        JOIN classes c ON c.id = s.class_id
        JOIN academic_sessions a ON a.id = s.academic_session_id
        WHERE s.id = ?
        """,
        (student_id,),
    ).fetchone()
    if row is None:
        raise DeskError("That student was not found.")
    return row


def student_public(row) -> dict:
    return {
        "id": row["id"],
        "admission_no": row["admission_no"],
        "name": row["name"],
        "father_name": row["father_name"],
        "class_id": row["class_id"],
        "class_name": row["class_name"],
        "section": row["section"],
        "academic_session_id": row["academic_session_id"],
        "session_name": row["session_name"],
        "phone": row["phone"],
        "status": row["status"],
    }


def waterfall(charges: list[dict], paid_paisa: int) -> tuple[list[dict], str | None]:
    rows = []
    credit = paid_paisa
    next_due = None
    for charge in sorted(charges, key=lambda item: (item["due_date"], item["id"])):
        net = int(charge["amount_paisa"]) - int(charge["concession_paisa"])
        applied = min(max(credit, 0), net)
        credit -= applied
        left = net - applied
        if left > 0 and next_due is None:
            next_due = charge["due_date"]
        rows.append(
            {
                "id": charge["id"],
                "head_name": charge["head_name"],
                "amount_paisa": charge["amount_paisa"],
                "concession_paisa": charge["concession_paisa"],
                "concession_reason": charge.get("concession_reason") or "",
                "due_date": charge["due_date"],
                "net_paisa": net,
                "paid_paisa": applied,
                "remaining_paisa": left,
                "source_package_id": charge.get("source_package_id"),
            }
        )
    return rows, next_due


def summarize(charges: list[dict], payments: list[dict], adjustments: list[dict]) -> dict:
    live = [item for item in payments if item["status"] != "cancelled"]
    total = sum(int(item["amount_paisa"]) - int(item["concession_paisa"]) for item in charges)
    paid = sum(int(item["amount_paisa"]) for item in live if item["status"] == "approved")
    paid += sum(int(item["amount_paisa"]) for item in adjustments)
    waiting = sum(int(item["amount_paisa"]) for item in live if item["status"] in WAITING)
    remaining = total - paid
    charge_rows, next_due = waterfall(charges, paid)
    return {
        "total_paisa": total,
        "paid_paisa": paid,
        "waiting_paisa": waiting,
        "remaining_paisa": remaining,
        "collectable_paisa": max(total - paid - waiting, 0),
        "next_due": next_due,
        "charges": charge_rows,
    }


def _load_money(conn, student_ids: list[int]) -> dict[int, dict]:
    grouped = {student_id: {"charges": [], "payments": [], "adjustments": []} for student_id in student_ids}
    if not student_ids:
        return grouped
    marks = ",".join("?" * len(student_ids))
    for row in conn.execute(
        f"SELECT * FROM student_charges WHERE student_id IN ({marks})",
        student_ids,
    ):
        grouped[row["student_id"]]["charges"].append(dict(row))
    for row in conn.execute(
        f"SELECT * FROM payments WHERE student_id IN ({marks}) ORDER BY id",
        student_ids,
    ):
        grouped[row["student_id"]]["payments"].append(dict(row))
    for row in conn.execute(
        f"SELECT * FROM adjustments WHERE student_id IN ({marks}) ORDER BY id",
        student_ids,
    ):
        grouped[row["student_id"]]["adjustments"].append(dict(row))
    return grouped


def _with_summary(student: dict, money: dict) -> dict:
    summary = summarize(money["charges"], money["payments"], money["adjustments"])
    summary.pop("charges", None)
    student.update(summary)
    student["can_delete"] = len(money["payments"]) == 0
    return student


def list_students(conn, search: str = "", class_id: int | None = None, session_id: int | None = None, status: str = "active") -> list[dict]:
    sql = """
        SELECT s.*, c.name AS class_name, a.name AS session_name
        FROM students s
        JOIN classes c ON c.id = s.class_id
        JOIN academic_sessions a ON a.id = s.academic_session_id
        WHERE 1 = 1
    """
    params: list = []
    if status and status != "all":
        sql += " AND s.status = ?"
        params.append(status)
    if class_id:
        sql += " AND s.class_id = ?"
        params.append(class_id)
    if session_id:
        sql += " AND s.academic_session_id = ?"
        params.append(session_id)
    if search and search.strip():
        like = f"%{search.strip()}%"
        sql += " AND (s.name LIKE ? OR s.admission_no LIKE ? OR s.father_name LIKE ? OR s.phone LIKE ?)"
        params.extend([like, like, like, like])
    sql += " ORDER BY s.name COLLATE NOCASE, s.admission_no"
    rows = [student_public(row) for row in conn.execute(sql, params)]
    money = _load_money(conn, [row["id"] for row in rows])
    return [_with_summary(row, money[row["id"]]) for row in rows]


def get_ledger(conn, student_id: int) -> dict:
    row = _require_student(conn, student_id)
    student = student_public(row)
    money = _load_money(conn, [student_id])[student_id]
    summary = summarize(money["charges"], money["payments"], money["adjustments"])
    names = {
        user["id"]: user["display_name"]
        for user in conn.execute("SELECT id, display_name FROM users")
    }
    payments = []
    for payment in money["payments"]:
        payments.append(
            {
                "id": payment["id"],
                "voucher_no": payment["voucher_no"],
                "amount_paisa": payment["amount_paisa"],
                "status": payment["status"],
                "status_label": _status_label(payment["status"]),
                "created_at": payment["created_at"],
                "approved_at": payment["approved_at"],
                "reject_reason": payment["reject_reason"] or "",
                "clerk_name": names.get(payment["created_by"], ""),
            }
        )
    adjustments = [
        {
            "id": item["id"],
            "amount_paisa": item["amount_paisa"],
            "reason": item["reason"],
            "created_at": item["created_at"],
            "created_by_name": names.get(item["created_by"], ""),
        }
        for item in money["adjustments"]
    ]
    student.update(summary)
    student["payments"] = payments
    student["adjustments"] = adjustments
    student["can_delete"] = len(money["payments"]) == 0
    return student


def create_student(conn, actor, payload: dict) -> dict:
    _staff(actor)
    admission = _clean(payload.get("admission_no"), "admission number", 30)
    name = _clean(payload.get("name"), "student name", 80)
    father = _clean(payload.get("father_name"), "father name", 80)
    section = " ".join(str(payload.get("section") or "").split())
    if len(section) > 20:
        raise DeskError("The section is too long.")
    phone = normalize_phone(payload.get("phone") or "")
    class_id = int(payload.get("class_id") or 0)
    session_id = int(payload.get("academic_session_id") or 0)
    _require_class(conn, class_id)
    _require_session(conn, session_id)
    try:
        cursor = conn.execute(
            """
            INSERT INTO students (
                admission_no, name, father_name, class_id, section, academic_session_id,
                phone, status, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
            """,
            (admission, name, father, class_id, section, session_id, phone, actor["id"], now_iso(), now_iso()),
        )
    except sqlite3.IntegrityError:
        raise DeskError("That admission number is already in use.") from None
    student_id = int(cursor.lastrowid)
    package_id = payload.get("package_id")
    if package_id:
        apply_package(conn, actor, student_id, int(package_id))
    audit(conn, actor, "create_student", f"Student added: {name} ({admission}).", "student", student_id, current_machine())
    return get_ledger(conn, student_id)


def update_student(conn, actor, student_id: int, payload: dict) -> dict:
    _staff(actor)
    current = _require_student(conn, student_id)
    admission = _clean(payload.get("admission_no"), "admission number", 30)
    name = _clean(payload.get("name"), "student name", 80)
    father = _clean(payload.get("father_name"), "father name", 80)
    section = " ".join(str(payload.get("section") or "").split())
    if len(section) > 20:
        raise DeskError("The section is too long.")
    phone = normalize_phone(payload.get("phone") or "")
    class_id = int(payload.get("class_id") or current["class_id"])
    session_id = int(payload.get("academic_session_id") or current["academic_session_id"])
    charge_count = conn.execute(
        "SELECT COUNT(*) AS c FROM student_charges WHERE student_id = ?",
        (student_id,),
    ).fetchone()["c"]
    if charge_count and (class_id != current["class_id"] or session_id != current["academic_session_id"]):
        raise DeskError("The class and session stay as they are after a fee package is applied.")
    _require_class(conn, class_id)
    _require_session(conn, session_id)
    try:
        conn.execute(
            """
            UPDATE students
            SET admission_no = ?, name = ?, father_name = ?, class_id = ?, section = ?,
                academic_session_id = ?, phone = ?, updated_at = ?
            WHERE id = ?
            """,
            (admission, name, father, class_id, section, session_id, phone, now_iso(), student_id),
        )
    except sqlite3.IntegrityError:
        raise DeskError("That admission number is already in use.") from None
    audit(conn, actor, "update_student", f"Student updated: {name} ({admission}).", "student", student_id, current_machine())
    return get_ledger(conn, student_id)


def set_student_status(conn, actor, student_id: int, status: str) -> dict:
    _staff(actor)
    if status not in ("active", "left"):
        raise DeskError("Mark the student active or left.")
    row = _require_student(conn, student_id)
    conn.execute("UPDATE students SET status = ?, updated_at = ? WHERE id = ?", (status, now_iso(), student_id))
    label = "left" if status == "left" else "active"
    audit(conn, actor, "set_status", f"{row['name']} marked {label}.", "student", student_id, current_machine())
    return get_ledger(conn, student_id)


def delete_student(conn, actor, student_id: int) -> None:
    _staff(actor)
    row = _require_student(conn, student_id)
    payments = conn.execute("SELECT COUNT(*) AS c FROM payments WHERE student_id = ?", (student_id,)).fetchone()["c"]
    if payments:
        raise DeskError("This student has fee vouchers, so the record stays. Mark the student as left.")
    history = conn.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM adjustments WHERE student_id = ?) +
            (SELECT COUNT(*) FROM sms_messages WHERE student_id = ?) AS c
        """,
        (student_id, student_id),
    ).fetchone()["c"]
    if history:
        raise DeskError("This student already has fee history, so the record stays. Mark the student as left.")
    conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    audit(conn, actor, "delete_student", f"Student removed: {row['name']} ({row['admission_no']}).", "student", student_id, current_machine())


def apply_package(conn, actor, student_id: int, package_id: int) -> dict:
    _staff(actor)
    student = _require_student(conn, student_id)
    package = conn.execute("SELECT * FROM fee_packages WHERE id = ?", (package_id,)).fetchone()
    if package is None:
        raise DeskError("That fee package was not found.")
    if package["class_id"] != student["class_id"] or package["academic_session_id"] != student["academic_session_id"]:
        raise DeskError("This fee package is for a different class or session.")
    already = conn.execute(
        "SELECT 1 FROM student_charges WHERE student_id = ? AND source_package_id = ?",
        (student_id, package_id),
    ).fetchone()
    if already:
        raise DeskError("This fee package is already on the student's record.")
    items = conn.execute(
        "SELECT * FROM fee_package_items WHERE package_id = ? ORDER BY due_date, id",
        (package_id,),
    ).fetchall()
    if not items:
        raise DeskError("This fee package has no fee heads.")
    for item in items:
        conn.execute(
            """
            INSERT INTO student_charges (
                student_id, head_name, amount_paisa, concession_paisa, due_date, source_package_id, created_at
            ) VALUES (?, ?, ?, 0, ?, ?, ?)
            """,
            (student_id, item["head_name"], item["amount_paisa"], item["due_date"], package_id, now_iso()),
        )
    audit(
        conn,
        actor,
        "apply_package",
        f"Fee package {package['name']} applied to {student['name']}.",
        "student",
        student_id,
        current_machine(),
    )
    return get_ledger(conn, student_id)


def set_concession(conn, actor, charge_id: int, amount_rupees, reason: str) -> dict:
    _admin(actor)
    charge = conn.execute("SELECT * FROM student_charges WHERE id = ?", (charge_id,)).fetchone()
    if charge is None:
        raise DeskError("That fee head was not found.")
    reason_text = _clean(reason, "reason", 200)
    rupees = _non_negative_rupees(amount_rupees)
    paisa = rupees * 100
    if paisa > charge["amount_paisa"]:
        raise DeskError("The concession cannot be more than that fee head.")
    conn.execute(
        "UPDATE student_charges SET concession_paisa = ?, concession_reason = ? WHERE id = ?",
        (paisa, reason_text, charge_id),
    )
    audit(
        conn,
        actor,
        "concession",
        f"Concession of {format_rs(paisa)} on {charge['head_name']}. {reason_text}",
        "charge",
        charge_id,
        current_machine(),
    )
    return get_ledger(conn, charge["student_id"])


def _non_negative_rupees(value) -> int:
    if isinstance(value, str) and value.strip() in {"0", "0.0"}:
        return 0
    if value == 0:
        return 0
    try:
        return parse_rupees(value) // 100
    except DeskError:
        text = str(value).strip().replace(",", "")
        if text == "0":
            return 0
        raise


def add_adjustment(conn, actor, student_id: int, direction: str, amount_rupees, reason: str) -> dict:
    _admin(actor)
    _require_student(conn, student_id)
    if direction not in ("credit", "reverse"):
        raise DeskError("Choose whether this correction reduces or increases what the student owes.")
    amount = parse_rupees(amount_rupees)
    signed = amount if direction == "credit" else -amount
    reason_text = _clean(reason, "reason", 200)
    cursor = conn.execute(
        """
        INSERT INTO adjustments (student_id, amount_paisa, reason, created_by, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (student_id, signed, reason_text, actor["id"], now_iso()),
    )
    verb = "credited" if signed > 0 else "reversed"
    audit(
        conn,
        actor,
        "adjustment",
        f"Correction {verb} {format_rs(abs(signed))}. {reason_text}",
        "adjustment",
        cursor.lastrowid,
        current_machine(),
    )
    return get_ledger(conn, student_id)


def _status_label(status: str) -> str:
    return {
        "unsubmitted": "In the drawer",
        "submitted": "Waiting for principal approval",
        "approved": "Approved",
        "rejected": "Sent back",
        "cancelled": "Cancelled",
    }.get(status, status)


def _next_voucher(conn) -> str:
    year = datetime.now().year
    prefix = setting(conn, "voucher_prefix", "PICS") or "PICS"
    row = conn.execute("SELECT last_number FROM voucher_counters WHERE year = ?", (year,)).fetchone()
    if row is None:
        number = 1
        conn.execute("INSERT INTO voucher_counters (year, last_number) VALUES (?, ?)", (year, number))
    else:
        number = int(row["last_number"]) + 1
        conn.execute("UPDATE voucher_counters SET last_number = ? WHERE year = ?", (number, year))
    return f"{prefix}-{year}-{number:05d}"


def record_payment(conn, actor, student_id: int, amount_rupees) -> dict:
    _clerk(actor)
    student = _require_student(conn, student_id)
    if student["status"] != "active":
        raise DeskError("This student is marked left. Mark them active before taking a fee.")
    amount = parse_rupees(amount_rupees)
    ledger = get_ledger(conn, student_id)
    if ledger["total_paisa"] <= 0:
        raise DeskError("This student has no fee package yet. Add the class fee first.")
    if ledger["collectable_paisa"] <= 0:
        raise DeskError("This student has no fee remaining to collect.")
    if amount > ledger["collectable_paisa"]:
        raise DeskError(
            f"That amount is more than the remaining fee ({format_rs(ledger['collectable_paisa'])})."
        )
    voucher_no = _next_voucher(conn)
    cursor = conn.execute(
        """
        INSERT INTO payments (
            student_id, amount_paisa, voucher_no, status, created_by, created_at
        ) VALUES (?, ?, ?, 'unsubmitted', ?, ?)
        """,
        (student_id, amount, voucher_no, actor["id"], now_iso()),
    )
    payment_id = int(cursor.lastrowid)
    audit(
        conn,
        actor,
        "record_payment",
        f"Cash recorded {format_rs(amount)} for {student['name']}. Voucher {voucher_no}.",
        "payment",
        payment_id,
        current_machine(),
    )
    return get_voucher(conn, actor, payment_id)


def _payment_row(conn, payment_id: int):
    row = conn.execute(
        """
        SELECT p.*, u.display_name AS clerk_name
        FROM payments p
        JOIN users u ON u.id = p.created_by
        WHERE p.id = ?
        """,
        (payment_id,),
    ).fetchone()
    if row is None:
        raise DeskError("That voucher was not found.")
    return row


def get_voucher(conn, actor, payment_id: int) -> dict:
    _staff(actor)
    payment = _payment_row(conn, payment_id)
    if actor["role"] != "admin" and payment["created_by"] != actor["id"]:
        raise DeskError("That voucher belongs to another clerk.")
    student = _require_student(conn, payment["student_id"])
    ledger = get_ledger(conn, payment["student_id"])
    if payment["status"] == "approved":
        remaining_if = ledger["remaining_paisa"]
    else:
        remaining_if = ledger["total_paisa"] - ledger["paid_paisa"] - payment["amount_paisa"]
    other_waiting = ledger["waiting_paisa"]
    if payment["status"] in WAITING:
        other_waiting -= payment["amount_paisa"]
    return {
        "id": payment["id"],
        "voucher_no": payment["voucher_no"],
        "status": payment["status"],
        "status_label": _status_label(payment["status"]),
        "created_at": payment["created_at"],
        "amount_paisa": payment["amount_paisa"],
        "student_id": student["id"],
        "student_name": student["name"],
        "father_name": student["father_name"],
        "admission_no": student["admission_no"],
        "class_name": student["class_name"],
        "section": student["section"],
        "phone": student["phone"],
        "clerk_name": payment["clerk_name"],
        "total_paisa": ledger["total_paisa"],
        "paid_paisa": ledger["paid_paisa"],
        "waiting_paisa": ledger["waiting_paisa"],
        "remaining_paisa": ledger["remaining_paisa"],
        "remaining_if_approved_paisa": remaining_if,
        "other_waiting_paisa": max(other_waiting, 0),
        "reject_reason": payment["reject_reason"] or "",
        "college": college_name(conn),
    }


def revise_payment(conn, actor, payment_id: int, amount_rupees) -> dict:
    _staff(actor)
    payment = _payment_row(conn, payment_id)
    if payment["status"] != "rejected":
        raise DeskError("Only a voucher the principal sent back can be corrected.")
    if actor["role"] != "admin" and payment["created_by"] != actor["id"]:
        raise DeskError("That voucher belongs to another clerk.")
    amount = parse_rupees(amount_rupees)
    ledger = get_ledger(conn, payment["student_id"])
    if amount > ledger["collectable_paisa"]:
        raise DeskError(
            f"That amount is more than the remaining fee ({format_rs(ledger['collectable_paisa'])})."
        )
    conn.execute(
        """
        UPDATE payments
        SET amount_paisa = ?, status = 'unsubmitted', submission_id = NULL,
            reject_reason = NULL, rejected_by = NULL, rejected_at = NULL
        WHERE id = ?
        """,
        (amount, payment_id),
    )
    audit(
        conn,
        actor,
        "revise_payment",
        f"Voucher {payment['voucher_no']} corrected to {format_rs(amount)} and put back in the drawer.",
        "payment",
        payment_id,
        current_machine(),
    )
    return get_voucher(conn, actor, payment_id)


def cancel_payment(conn, actor, payment_id: int) -> dict:
    _staff(actor)
    payment = _payment_row(conn, payment_id)
    if payment["status"] not in ("unsubmitted", "rejected"):
        raise DeskError("A voucher handed to the principal cannot be cancelled here.")
    if actor["role"] != "admin" and payment["created_by"] != actor["id"]:
        raise DeskError("That voucher belongs to another clerk.")
    conn.execute("UPDATE payments SET status = 'cancelled' WHERE id = ?", (payment_id,))
    audit(conn, actor, "cancel_payment", f"Voucher {payment['voucher_no']} cancelled.", "payment", payment_id, current_machine())
    return get_voucher(conn, actor, payment_id)


def desk_for(conn, actor) -> dict:
    _staff(actor)
    rows = conn.execute(
        """
        SELECT p.*, s.name AS student_name, s.admission_no, c.name AS class_name
        FROM payments p
        JOIN students s ON s.id = p.student_id
        JOIN classes c ON c.id = s.class_id
        WHERE p.created_by = ? AND p.status IN ('unsubmitted', 'submitted', 'rejected')
        ORDER BY p.id
        """,
        (actor["id"],),
    ).fetchall()
    groups = {"unsubmitted": [], "submitted": [], "rejected": []}
    for row in rows:
        groups[row["status"]].append(_desk_line(row))
    open_rows = conn.execute(
        """
        SELECT id FROM submissions
        WHERE clerk_id = ? AND status = 'open'
        ORDER BY id DESC
        """,
        (actor["id"],),
    ).fetchall()
    return {
        "unsubmitted": _group(groups["unsubmitted"]),
        "submitted": _group(groups["submitted"]),
        "rejected": _group(groups["rejected"]),
        "open_submissions": [_submission_detail(conn, row["id"]) for row in open_rows],
    }


def _desk_line(row) -> dict:
    return {
        "id": row["id"],
        "voucher_no": row["voucher_no"],
        "student_name": row["student_name"],
        "admission_no": row["admission_no"],
        "class_name": row["class_name"],
        "amount_paisa": row["amount_paisa"],
        "created_at": row["created_at"],
        "reject_reason": row["reject_reason"] or "",
        "status": row["status"],
    }


def _group(rows: list[dict]) -> dict:
    return {
        "count": len(rows),
        "total_paisa": sum(row["amount_paisa"] for row in rows),
        "rows": rows,
    }


def submit_bundle(conn, actor) -> dict:
    _clerk(actor)
    rows = conn.execute(
        """
        SELECT * FROM payments
        WHERE created_by = ? AND status = 'unsubmitted'
        ORDER BY id
        """,
        (actor["id"],),
    ).fetchall()
    if not rows:
        raise DeskError("There is no cash in the drawer to hand over.")
    cursor = conn.execute(
        """
        INSERT INTO submissions (clerk_id, submitted_at, status)
        VALUES (?, ?, 'open')
        """,
        (actor["id"], now_iso()),
    )
    submission_id = int(cursor.lastrowid)
    ids = [row["id"] for row in rows]
    conn.execute(
        f"UPDATE payments SET status = 'submitted', submission_id = ? WHERE id IN ({','.join('?' * len(ids))})",
        [submission_id, *ids],
    )
    total = sum(row["amount_paisa"] for row in rows)
    audit(
        conn,
        actor,
        "submit_bundle",
        f"Cash handed over. {len(rows)} voucher(s), {format_rs(total)}.",
        "submission",
        submission_id,
        current_machine(),
    )
    return _submission_detail(conn, submission_id)


def list_open_submissions(conn, actor) -> list[dict]:
    _admin(actor)
    rows = conn.execute(
        "SELECT id FROM submissions WHERE status = 'open' ORDER BY id"
    ).fetchall()
    return [_submission_detail(conn, row["id"]) for row in rows]


def cash_overview(conn, actor) -> dict:
    """Cash the principal can count, plus cash the clerk has recorded but not handed over."""
    ready = list_open_submissions(conn, actor)
    rows = conn.execute(
        """
        SELECT p.id, p.voucher_no, p.amount_paisa, p.created_at,
               s.name AS student_name, s.admission_no,
               c.name AS class_name,
               u.display_name AS clerk_name
        FROM payments p
        JOIN students s ON s.id = p.student_id
        JOIN classes c ON c.id = s.class_id
        JOIN users u ON u.id = p.created_by
        WHERE p.status = 'unsubmitted'
        ORDER BY p.id
        """
    ).fetchall()
    with_clerk = [dict(row) for row in rows]
    return {
        "ready": ready,
        "ready_total_paisa": sum(item["expected_paisa"] for item in ready),
        "ready_vouchers": sum(item["voucher_count"] for item in ready),
        "with_clerk": with_clerk,
        "with_clerk_total_paisa": sum(item["amount_paisa"] for item in with_clerk),
        "with_clerk_count": len(with_clerk),
    }


def get_submission(conn, actor, submission_id: int) -> dict:
    _staff(actor)
    detail = _submission_detail(conn, submission_id)
    if actor["role"] != "admin" and detail["clerk_id"] != actor["id"]:
        raise DeskError("That cash bundle belongs to another clerk.")
    return detail


def _submission_detail(conn, submission_id: int) -> dict:
    sub = conn.execute(
        """
        SELECT b.*, u.display_name AS clerk_name
        FROM submissions b
        JOIN users u ON u.id = b.clerk_id
        WHERE b.id = ?
        """,
        (submission_id,),
    ).fetchone()
    if sub is None:
        raise DeskError("That cash bundle was not found.")
    lines = [
        dict(row)
        for row in conn.execute(
            """
            SELECT p.*, s.name AS student_name, s.father_name, s.admission_no, s.section,
                   c.name AS class_name
            FROM payments p
            JOIN students s ON s.id = p.student_id
            JOIN classes c ON c.id = s.class_id
            WHERE p.submission_id = ?
            ORDER BY p.id
            """,
            (submission_id,),
        )
    ]
    pending = [line for line in lines if line["status"] == "submitted"]
    approved = [line for line in lines if line["status"] == "approved"]
    rejected = [line for line in lines if line["status"] == "rejected"]
    expected = sum(line["amount_paisa"] for line in pending) + sum(line["amount_paisa"] for line in approved)
    in_bundle = pending + approved
    counted = sub["counted_paisa"]
    difference = None if counted is None else counted - expected
    return {
        "id": sub["id"],
        "clerk_id": sub["clerk_id"],
        "clerk_name": sub["clerk_name"],
        "submitted_at": sub["submitted_at"],
        "status": sub["status"],
        "counted_paisa": counted,
        "expected_paisa": expected,
        "pending_paisa": sum(line["amount_paisa"] for line in pending),
        "approved_paisa": sum(line["amount_paisa"] for line in approved),
        "rejected_paisa": sum(line["amount_paisa"] for line in rejected),
        "difference_paisa": difference,
        "exact_match": counted is not None and difference == 0,
        "voucher_count": len(in_bundle),
        "student_count": len({line["student_id"] for line in in_bundle}),
        "lines": [
            {
                "id": line["id"],
                "voucher_no": line["voucher_no"],
                "student_id": line["student_id"],
                "student_name": line["student_name"],
                "father_name": line["father_name"],
                "admission_no": line["admission_no"],
                "class_name": line["class_name"],
                "section": line["section"],
                "amount_paisa": line["amount_paisa"],
                "status": line["status"],
                "status_label": _status_label(line["status"]),
                "reject_reason": line["reject_reason"] or "",
                "created_at": line["created_at"],
            }
            for line in lines
        ],
        "college": college_name(conn),
    }


def _require_open_submission(conn, submission_id: int):
    sub = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
    if sub is None:
        raise DeskError("That cash bundle was not found.")
    if sub["status"] != "open":
        raise DeskError("This cash bundle is already closed.")
    return sub


def set_counted(conn, actor, submission_id: int, amount_rupees) -> dict:
    _admin(actor)
    _require_open_submission(conn, submission_id)
    counted = parse_counted(amount_rupees)
    conn.execute("UPDATE submissions SET counted_paisa = ? WHERE id = ?", (counted, submission_id))
    audit(
        conn,
        actor,
        "set_counted",
        f"Counted cash entered as {format_rs(counted)} for bundle {submission_id}.",
        "submission",
        submission_id,
        current_machine(),
    )
    _maybe_close(conn, actor, submission_id)
    return _submission_detail(conn, submission_id)


def _expected_amounts(conn, submission_id: int) -> tuple[int, int, int]:
    row = conn.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN status IN ('submitted', 'approved') THEN amount_paisa END), 0) AS expected,
            COALESCE(SUM(CASE WHEN status = 'approved' THEN amount_paisa END), 0) AS approved,
            COALESCE(SUM(CASE WHEN status = 'submitted' THEN 1 ELSE 0 END), 0) AS pending_count
        FROM payments
        WHERE submission_id = ?
        """,
        (submission_id,),
    ).fetchone()
    return int(row["expected"]), int(row["approved"]), int(row["pending_count"])


def _mismatch() -> DeskError:
    return DeskError(
        "The counted cash does not match the system total. Reject the voucher that is wrong, set those notes aside, and count again."
    )


def _require_count_match(conn, submission_id: int) -> None:
    sub = conn.execute("SELECT counted_paisa FROM submissions WHERE id = ?", (submission_id,)).fetchone()
    if sub["counted_paisa"] is None:
        raise DeskError("Enter the counted cash before approving.")
    expected, _, _ = _expected_amounts(conn, submission_id)
    if int(sub["counted_paisa"]) != expected:
        raise _mismatch()


def approve_all(conn, actor, submission_id: int) -> dict:
    _admin(actor)
    _require_open_submission(conn, submission_id)
    _require_count_match(conn, submission_id)
    pending = conn.execute(
        "SELECT id FROM payments WHERE submission_id = ? AND status = 'submitted' ORDER BY id",
        (submission_id,),
    ).fetchall()
    for row in pending:
        _post_payment(conn, actor, int(row["id"]))
    _maybe_close(conn, actor, submission_id)
    audit(conn, actor, "approve_all", f"Approved the remaining vouchers in bundle {submission_id}.", "submission", submission_id, current_machine())
    return _submission_detail(conn, submission_id)


def approve_one(conn, actor, payment_id: int) -> dict:
    _admin(actor)
    payment = _payment_row(conn, payment_id)
    if payment["status"] != "submitted" or not payment["submission_id"]:
        raise DeskError("This voucher is not waiting for approval.")
    submission_id = int(payment["submission_id"])
    _require_open_submission(conn, submission_id)
    sub = conn.execute("SELECT counted_paisa FROM submissions WHERE id = ?", (submission_id,)).fetchone()
    if sub["counted_paisa"] is None:
        raise DeskError("Enter the counted cash before approving.")
    expected, _, pending_count = _expected_amounts(conn, submission_id)
    if pending_count == 1 and int(sub["counted_paisa"]) != expected:
        raise _mismatch()
    _post_payment(conn, actor, payment_id)
    _maybe_close(conn, actor, submission_id)
    return _submission_detail(conn, submission_id)


def reject_one(conn, actor, payment_id: int, reason: str) -> dict:
    _admin(actor)
    payment = _payment_row(conn, payment_id)
    if payment["status"] != "submitted" or not payment["submission_id"]:
        raise DeskError("This voucher is not waiting for approval.")
    reason_text = _clean(reason, "reason", 200)
    submission_id = int(payment["submission_id"])
    _require_open_submission(conn, submission_id)
    conn.execute(
        """
        UPDATE payments
        SET status = 'rejected', reject_reason = ?, rejected_by = ?, rejected_at = ?
        WHERE id = ?
        """,
        (reason_text, actor["id"], now_iso(), payment_id),
    )
    audit(
        conn,
        actor,
        "reject_payment",
        f"Sent back {payment['voucher_no']} ({format_rs(payment['amount_paisa'])}). {reason_text}",
        "payment",
        payment_id,
        current_machine(),
    )
    _maybe_close(conn, actor, submission_id)
    detail = _submission_detail(conn, submission_id)
    detail["set_aside_paisa"] = payment["amount_paisa"]
    detail["set_aside_message"] = (
        f"Set aside {format_rs(payment['amount_paisa'])} from the cash. Those notes do not stay in this bundle."
    )
    return detail


def _post_payment(conn, actor, payment_id: int) -> None:
    payment = _payment_row(conn, payment_id)
    if payment["status"] != "submitted":
        raise DeskError("This voucher is not waiting for approval.")
    conn.execute(
        """
        UPDATE payments
        SET status = 'approved', approved_by = ?, approved_at = ?
        WHERE id = ?
        """,
        (actor["id"], now_iso(), payment_id),
    )
    _queue_payment_sms(conn, payment_id)
    audit(
        conn,
        actor,
        "approve_payment",
        f"Approved {payment['voucher_no']} for {format_rs(payment['amount_paisa'])}.",
        "payment",
        payment_id,
        current_machine(),
    )


def _maybe_close(conn, actor, submission_id: int) -> bool:
    sub = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
    if sub is None or sub["status"] != "open" or sub["counted_paisa"] is None:
        return False
    _, approved, pending_count = _expected_amounts(conn, submission_id)
    if pending_count == 0 and int(sub["counted_paisa"]) == approved:
        conn.execute(
            "UPDATE submissions SET status = 'closed', closed_at = ? WHERE id = ?",
            (now_iso(), submission_id),
        )
        audit(conn, actor, "close_bundle", f"Cash bundle {submission_id} closed.", "submission", submission_id, current_machine())
        return True
    return False


def _sample_fields() -> dict:
    return {name: "x" for name in TEMPLATE_FIELDS}


def _check_template(template: str, label: str) -> str:
    text = (template or "").strip()
    if not text:
        raise DeskError(f"Write the {label}.")
    try:
        text.format(**_sample_fields())
    except KeyError as exc:
        raise DeskError(f"The {label} uses an unknown field {exc}.") from None
    except ValueError:
        raise DeskError(f"The {label} has a broken bracket.") from None
    return text


def sms_settings_view(conn) -> dict:
    from pics_fee.sms import load_sms_config

    config = load_sms_config(conn)
    key = config["api_key"]
    return {
        "test_mode": config["test_mode"],
        "api_url": config["api_url"],
        "sender": config["sender"],
        "key_set": bool(key),
        "key_masked": ("••••" + key[-4:]) if key else "",
        "payment_template": config["payment_template"],
        "reminder_template": config["reminder_template"],
        "fields": list(TEMPLATE_FIELDS),
    }


def save_sms_settings(conn, actor, payload: dict) -> dict:
    _admin(actor)
    from pics_fee.sms import load_sms_config

    test_mode = bool(payload.get("test_mode", True))
    url = str(payload.get("api_url") or "").strip()
    sender = str(payload.get("sender") or "").strip()
    if len(sender) > 20:
        raise DeskError("The sender mask can be at most 20 characters.")
    payment = _check_template(payload.get("payment_template"), "payment message")
    reminder = _check_template(payload.get("reminder_template"), "reminder message")
    current = load_sms_config(conn)
    incoming = payload.get("api_key")
    key = current["api_key"]
    if incoming:
        key = str(incoming).strip()
    if not test_mode:
        if not url or not sender:
            raise DeskError("Enter the SMS address and sender mask before turning off test mode.")
        if not key:
            raise DeskError("Enter the SMS key before turning off test mode.")
    set_setting(conn, "sms_test_mode", "1" if test_mode else "0")
    set_setting(conn, "sms_api_url", url)
    set_setting(conn, "sms_sender", sender)
    set_setting(conn, "sms_template_payment", payment)
    set_setting(conn, "sms_template_reminder", reminder)
    if incoming:
        set_setting(conn, "sms_api_key", seal_secret(str(incoming).strip()))
    audit(conn, actor, "sms_settings", "SMS settings updated.", "settings", None, current_machine())
    return sms_settings_view(conn)


def _render(template: str, fields: dict) -> str:
    try:
        return template.format(**fields)
    except (KeyError, ValueError) as exc:
        raise DeskError(f"The message template could not be filled in ({exc}).") from None


def _message_fields(conn, student_row, ledger: dict, payment=None) -> dict:
    due = "Paid in full" if ledger["remaining_paisa"] <= 0 else format_date(ledger["next_due"])
    return {
        "college": college_name(conn),
        "student": student_row["name"],
        "father": student_row["father_name"],
        "class_name": student_row["class_name"],
        "section": student_row["section"] or "",
        "admission_no": student_row["admission_no"],
        "amount": format_rs(payment["amount_paisa"]) if payment else "",
        "voucher": payment["voucher_no"] if payment else "",
        "total": format_rs(ledger["total_paisa"]),
        "paid": format_rs(ledger["paid_paisa"]),
        "remaining": format_rs(max(ledger["remaining_paisa"], 0)),
        "due_date": due,
        "date": format_date(now_iso()),
    }


def _queue_payment_sms(conn, payment_id: int) -> None:
    existing = conn.execute(
        "SELECT id FROM sms_messages WHERE payment_id = ? AND kind = 'payment'",
        (payment_id,),
    ).fetchone()
    if existing:
        return
    payment = _payment_row(conn, payment_id)
    student = _require_student(conn, payment["student_id"])
    ledger = get_ledger(conn, payment["student_id"])
    template = setting(conn, "sms_template_payment", "")
    try:
        phone = to_sms_phone(student["phone"])
        body = _render(template, _message_fields(conn, student, ledger, payment))
    except DeskError as exc:
        conn.execute(
            """
            INSERT INTO sms_messages (
                student_id, payment_id, phone, body, kind, status, error, created_at
            ) VALUES (?, ?, ?, ?, 'payment', 'failed', ?, ?)
            """,
            (student["id"], payment_id, student["phone"], "", str(exc), now_iso()),
        )
        return
    conn.execute(
        """
        INSERT INTO sms_messages (
            student_id, payment_id, phone, body, kind, status, created_at
        ) VALUES (?, ?, ?, ?, 'payment', 'queued', ?)
        """,
        (student["id"], payment_id, phone, body, now_iso()),
    )


def reminder_candidates(conn, within_days: int = 7, include_all: bool = False) -> list[dict]:
    within_days = max(0, min(int(within_days), 3650))
    today = datetime.now().date()
    limit = today + timedelta(days=within_days)
    template = setting(conn, "sms_template_reminder", "")
    rows = []
    for student in list_students(conn, status="all"):
        if student["remaining_paisa"] <= 0:
            continue
        due = student["next_due"]
        if not include_all:
            if not due:
                continue
            due_date = datetime.strptime(due, "%Y-%m-%d").date()
            if due_date > limit:
                continue
        full = _require_student(conn, student["id"])
        ledger = {
            "total_paisa": student["total_paisa"],
            "paid_paisa": student["paid_paisa"],
            "remaining_paisa": student["remaining_paisa"],
            "next_due": student["next_due"],
        }
        try:
            phone = to_sms_phone(full["phone"])
            body = _render(template, _message_fields(conn, full, ledger))
            error = ""
        except DeskError as exc:
            phone = full["phone"]
            body = ""
            error = str(exc)
        rows.append(
            {
                "student_id": student["id"],
                "student_name": student["name"],
                "admission_no": student["admission_no"],
                "class_name": student["class_name"],
                "phone": phone,
                "remaining_paisa": student["remaining_paisa"],
                "next_due": student["next_due"],
                "body": body,
                "error": error,
            }
        )
    rows.sort(key=lambda item: (item["next_due"] or "9999", item["student_name"]))
    return rows


def queue_reminders(conn, actor, student_ids: list[int]) -> int:
    _admin(actor)
    allowed = {row["student_id"]: row for row in reminder_candidates(conn, include_all=True)}
    count = 0
    for student_id in student_ids:
        row = allowed.get(int(student_id))
        if row is None or not row["body"]:
            continue
        conn.execute(
            """
            INSERT INTO sms_messages (student_id, phone, body, kind, status, created_at)
            VALUES (?, ?, ?, 'reminder', 'queued', ?)
            """,
            (row["student_id"], row["phone"], row["body"], now_iso()),
        )
        count += 1
    audit(conn, actor, "queue_reminders", f"Queued {count} fee reminder(s).", "sms", None, current_machine())
    return count


def list_sms(conn, limit: int = 200) -> list[dict]:
    rows = conn.execute(
        """
        SELECT m.*, s.name AS student_name, s.admission_no
        FROM sms_messages m
        LEFT JOIN students s ON s.id = m.student_id
        ORDER BY m.id DESC
        LIMIT ?
        """,
        (max(1, min(int(limit), 500)),),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "student_id": row["student_id"],
            "student_name": row["student_name"] or "",
            "admission_no": row["admission_no"] or "",
            "phone": row["phone"],
            "body": row["body"],
            "kind": row["kind"],
            "status": row["status"],
            "provider_ref": row["provider_ref"] or "",
            "error": row["error"] or "",
            "created_at": row["created_at"],
            "sent_at": row["sent_at"],
        }
        for row in rows
    ]


def retry_sms(conn, actor, message_id: int) -> None:
    _admin(actor)
    row = conn.execute("SELECT * FROM sms_messages WHERE id = ?", (message_id,)).fetchone()
    if row is None:
        raise DeskError("That message was not found.")
    if row["status"] != "failed":
        raise DeskError("Only a failed message can be sent again.")
    conn.execute("UPDATE sms_messages SET status = 'queued', error = NULL WHERE id = ?", (message_id,))
    audit(conn, actor, "retry_sms", f"Will try the message to {row['phone']} again.", "sms", message_id, current_machine())


def report(conn, date_from: str, date_to: str) -> dict:
    start = parse_date(date_from)
    end = parse_date(date_to)
    if start > end:
        raise DeskError("The start date is after the end date.")
    payments = [
        {
            "id": row["id"],
            "voucher_no": row["voucher_no"],
            "student_name": row["student_name"],
            "admission_no": row["admission_no"],
            "class_name": row["class_name"],
            "amount_paisa": row["amount_paisa"],
            "approved_at": row["approved_at"],
            "clerk_name": row["clerk_name"],
        }
        for row in conn.execute(
            """
            SELECT p.*, s.name AS student_name, s.admission_no, c.name AS class_name,
                   u.display_name AS clerk_name
            FROM payments p
            JOIN students s ON s.id = p.student_id
            JOIN classes c ON c.id = s.class_id
            JOIN users u ON u.id = p.created_by
            WHERE p.status = 'approved' AND date(p.approved_at) >= ? AND date(p.approved_at) <= ?
            ORDER BY p.approved_at, p.id
            """,
            (start, end),
        )
    ]
    waiting_row = conn.execute(
        """
        SELECT COALESCE(SUM(amount_paisa), 0) AS total, COUNT(*) AS count
        FROM payments
        WHERE status IN ('unsubmitted', 'submitted')
        """
    ).fetchone()
    outstanding = []
    outstanding_total = 0
    for student in list_students(conn, status="all"):
        if student["remaining_paisa"] > 0:
            outstanding_total += student["remaining_paisa"]
            outstanding.append(
                {
                    "student_id": student["id"],
                    "student_name": student["name"],
                    "admission_no": student["admission_no"],
                    "class_name": student["class_name"],
                    "phone": student["phone"],
                    "total_paisa": student["total_paisa"],
                    "paid_paisa": student["paid_paisa"],
                    "remaining_paisa": student["remaining_paisa"],
                    "next_due": student["next_due"],
                    "status": student["status"],
                }
            )
    outstanding.sort(key=lambda item: item["remaining_paisa"], reverse=True)
    return {
        "date_from": start,
        "date_to": end,
        "approved_total_paisa": sum(item["amount_paisa"] for item in payments),
        "approved_count": len(payments),
        "student_count": len({item["admission_no"] for item in payments}),
        "payments": payments,
        "waiting_total_paisa": int(waiting_row["total"]),
        "waiting_count": int(waiting_row["count"]),
        "outstanding_total_paisa": outstanding_total,
        "outstanding_count": len(outstanding),
        "outstanding": outstanding,
    }


def sms_count(conn, payment_id: int | None = None) -> int:
    if payment_id is None:
        return conn.execute("SELECT COUNT(*) AS c FROM sms_messages").fetchone()["c"]
    return conn.execute(
        "SELECT COUNT(*) AS c FROM sms_messages WHERE payment_id = ?",
        (payment_id,),
    ).fetchone()["c"]


def make_backup(actor=None, manual: bool = False) -> str:
    import sqlite3

    from pics_fee.db import connect, init_db, transaction
    from pics_fee.paths import backup_dir

    init_db()
    folder = backup_dir()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = folder / f"fee-{stamp}.db"
    sequence = 1
    while dest.exists():
        dest = folder / f"fee-{stamp}-{sequence}.db"
        sequence += 1
    source = connect()
    try:
        target = sqlite3.connect(dest)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()
    files = sorted(folder.glob("fee-*.db"), key=lambda path: path.stat().st_mtime, reverse=True)
    for old in files[30:]:
        old.unlink(missing_ok=True)
    if manual and actor:
        with transaction() as conn:
            audit(conn, actor, "backup", f"Backup saved: {dest.name}.", "backup", None, current_machine())
    return str(dest)


def backup_info() -> dict:
    from pics_fee.paths import backup_dir, data_dir

    folder = backup_dir()
    files = sorted(folder.glob("fee-*.db"), key=lambda path: path.stat().st_mtime, reverse=True)
    return {
        "data_dir": str(data_dir()),
        "backup_dir": str(folder),
        "last_backup": files[0].name if files else "",
        "college": COLLEGE_NAME,
    }
