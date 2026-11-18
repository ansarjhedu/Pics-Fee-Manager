from __future__ import annotations

import json
from datetime import datetime


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def audit(conn, actor, action: str, summary: str, entity: str | None = None, entity_id: int | None = None, machine: str | None = None, extra: dict | None = None) -> None:
    detail = {"summary": summary}
    if extra:
        detail.update(extra)
    conn.execute(
        """
        INSERT INTO audit_log (user_id, username, action, entity, entity_id, detail, machine, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            None if actor is None else actor.get("id"),
            None if actor is None else actor.get("username"),
            action,
            entity,
            entity_id,
            json.dumps(detail, ensure_ascii=False),
            machine or "",
            now_iso(),
        ),
    )
