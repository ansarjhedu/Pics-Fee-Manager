from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from pics_fee.audit import audit, now_iso
from pics_fee.db import setting, transaction
from pics_fee.paths import sms_log_path
from pics_fee.security import unseal_secret


def load_sms_config(conn) -> dict:
    sealed = setting(conn, "sms_api_key", "")
    key = ""
    if sealed:
        try:
            key = unseal_secret(sealed)
        except OSError:
            key = ""
    return {
        "api_url": setting(conn, "sms_api_url", ""),
        "api_key": key,
        "sender": setting(conn, "sms_sender", ""),
        "test_mode": setting(conn, "sms_test_mode", "1") == "1",
        "payment_template": setting(conn, "sms_template_payment", ""),
        "reminder_template": setting(conn, "sms_template_reminder", ""),
    }


def deliver(config: dict, phone: str, message: str) -> tuple[bool, str, str]:
    """Send one SMS. Returns ok, provider reference, error text."""
    url = (config.get("api_url") or "").strip()
    key = config.get("api_key") or ""
    sender = config.get("sender") or ""
    if not url:
        return False, "", "The SMS address is empty."
    try:
        if any(token in url for token in ("{phone}", "{message}", "{key}", "{sender}")):
            full = url.format(
                phone=urllib.parse.quote(phone),
                message=urllib.parse.quote(message),
                key=urllib.parse.quote(key),
                sender=urllib.parse.quote(sender),
            )
            request = urllib.request.Request(full, method="GET")
        else:
            payload = json.dumps(
                {"api_key": key, "sender": sender, "phone": phone, "message": message}
            ).encode("utf-8")
            request = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read(500).decode("utf-8", errors="replace")
            return True, body.strip() or "ok", ""
    except urllib.error.HTTPError as exc:
        detail = exc.read(300).decode("utf-8", errors="replace")
        return False, "", f"The SMS service refused the message ({exc.code}). {detail}".strip()
    except Exception as exc:  # network and URL errors stay on the message row
        return False, "", str(exc)


def _log_test(phone: str, body: str) -> None:
    path = sms_log_path()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{now_iso()} {phone}\n{body}\n---\n")


def process_sms_queue(actor=None, machine: str | None = None) -> int:
    """Send every queued message. Test mode writes a local log and does not call the gateway."""
    with transaction() as conn:
        rows = [dict(row) for row in conn.execute("SELECT * FROM sms_messages WHERE status = 'queued' ORDER BY id")]
        config = load_sms_config(conn)
    sent = 0
    for row in rows:
        if config["test_mode"]:
            _log_test(row["phone"], row["body"])
            ok, ref, err = True, "TEST-NOT-SENT", ""
        else:
            ok, ref, err = deliver(config, row["phone"], row["body"])
        with transaction() as conn:
            current = conn.execute("SELECT status FROM sms_messages WHERE id = ?", (row["id"],)).fetchone()
            if current is None or current["status"] != "queued":
                continue
            if ok:
                conn.execute(
                    """
                    UPDATE sms_messages
                    SET status = 'sent', provider_ref = ?, error = NULL, sent_at = ?
                    WHERE id = ?
                    """,
                    (ref[:500], now_iso(), row["id"]),
                )
                sent += 1
                audit(
                    conn,
                    actor,
                    "sms_sent",
                    f"Message logged for {row['phone']}" if config["test_mode"] else f"SMS sent to {row['phone']}",
                    "sms",
                    row["id"],
                    machine,
                )
            else:
                conn.execute(
                    "UPDATE sms_messages SET status = 'failed', error = ? WHERE id = ?",
                    (err[:500], row["id"]),
                )
                audit(conn, actor, "sms_failed", f"SMS failed for {row['phone']}: {err[:180]}", "sms", row["id"], machine)
    return sent
