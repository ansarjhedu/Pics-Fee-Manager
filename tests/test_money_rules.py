from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import pics_fee.services as services
from pics_fee.constants import COLLEGE_NAME
from pics_fee.db import transaction
from pics_fee.errors import DeskError
from pics_fee.phones import normalize_phone, to_sms_phone
from pics_fee.printing import handover_html, voucher_html
from pics_fee.server import create_app
from pics_fee.sms import process_sms_queue
from pics_fee.textfmt import format_rs, rupees_in_words


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PICS_DATA_DIR", str(tmp_path))
    from pics_fee.db import init_db

    init_db()
    return tmp_path


def _school():
    with transaction() as conn:
        admin = services.create_initial_admin(conn, "principal", "principal1", "The Principal")
        clerk = services.create_clerk(conn, admin, "clerk", "clerkpass1", "Fee Clerk")
        klass = services.add_class(conn, admin, "FSc Pre-Medical")
        session = services.add_session(conn, admin, "2026-27")
        package = services.create_package(
            conn,
            admin,
            "Yearly",
            klass["id"],
            session["id"],
            [
                {"head_name": "Funds", "amount_rupees": 2000, "due_date": "2026-03-01"},
                {"head_name": "Tuition", "amount_rupees": 10000, "due_date": "2026-04-10"},
            ],
        )
        student = services.create_student(
            conn,
            clerk,
            {
                "admission_no": "1001",
                "name": "Ali Raza",
                "father_name": "Raza Khan",
                "class_id": klass["id"],
                "section": "A",
                "academic_session_id": session["id"],
                "phone": "03001234567",
                "package_id": package["id"],
            },
        )
    return {"admin": admin, "clerk": clerk, "package": package, "student": student}


def _pay(actor, student_id, rupees):
    with transaction() as conn:
        return services.record_payment(conn, actor, student_id, rupees)


def _submit(actor):
    with transaction() as conn:
        return services.submit_bundle(conn, actor)


def test_class_board_keeps_sections_with_students():
    school = _school()
    class_id = school["student"]["class_id"]
    with transaction() as conn:
        services.add_section(conn, school["admin"], class_id, "B")
        board = services.class_board(conn, status="active")
    klass = next(row for row in board if row["id"] == class_id)
    assert klass["students"] == 1
    names = {item["name"] for item in klass["sections"]}
    assert names == {"A", "B"}
    assert next(item["students"] for item in klass["sections"] if item["name"] == "A") == 1
    assert next(item["students"] for item in klass["sections"] if item["name"] == "B") == 0


def test_principal_sees_cash_before_handover():
    school = _school()
    _pay(school["clerk"], school["student"]["id"], 5000)
    with transaction() as conn:
        overview = services.cash_overview(conn, school["admin"])
    assert overview["ready"] == []
    assert overview["with_clerk_count"] == 1
    assert overview["with_clerk_total_paisa"] == 500000
    assert overview["with_clerk"][0]["student_name"] == "Ali Raza"
    _submit(school["clerk"])
    with transaction() as conn:
        overview = services.cash_overview(conn, school["admin"])
    assert overview["with_clerk_count"] == 0
    assert overview["ready_total_paisa"] == 500000
    assert overview["ready_vouchers"] == 1


def test_money_words_and_pakistani_grouping():
    assert format_rs(500000) == "Rs 5,000"
    assert format_rs(10000000) == "Rs 1,00,000"
    assert rupees_in_words(500000) == "Rupees Five Thousand Only"
    assert rupees_in_words(12_500_000) == "Rupees One Lakh Twenty Five Thousand Only"
    assert normalize_phone("+92 300 1234567") == "03001234567"
    assert to_sms_phone("03001234567") == "923001234567"


def test_partial_payment_waterfall_and_remaining():
    school = _school()
    voucher = _pay(school["clerk"], school["student"]["id"], 2500)
    assert voucher["status"] == "unsubmitted"
    assert "PICS-" in voucher["voucher_no"]
    _submit(school["clerk"])
    with transaction() as conn:
        bundle = services.list_open_submissions(conn, school["admin"])[0]
        services.set_counted(conn, school["admin"], bundle["id"], 2500)
        services.approve_all(conn, school["admin"], bundle["id"])
        ledger = services.get_ledger(conn, school["student"]["id"])
    heads = {row["head_name"]: row for row in ledger["charges"]}
    assert heads["Funds"]["remaining_paisa"] == 0
    assert heads["Tuition"]["paid_paisa"] == 50000
    assert heads["Tuition"]["remaining_paisa"] == 950000
    assert ledger["paid_paisa"] == 250000
    assert ledger["remaining_paisa"] == 950000
    assert ledger["waiting_paisa"] == 0
    assert ledger["next_due"] == "2026-04-10"


def test_overpay_and_waiting_cash_are_refused():
    school = _school()
    with pytest.raises(DeskError):
        _pay(school["clerk"], school["student"]["id"], 12001)
    _pay(school["clerk"], school["student"]["id"], 2000)
    with pytest.raises(DeskError):
        _pay(school["clerk"], school["student"]["id"], 10001)


def test_approve_all_requires_exact_cash_and_rejection_lowers_the_total():
    school = _school()
    first = _pay(school["clerk"], school["student"]["id"], 1000)
    second = _pay(school["clerk"], school["student"]["id"], 2000)
    bundle = _submit(school["clerk"])
    assert bundle["expected_paisa"] == 300000
    assert bundle["student_count"] == 1
    assert bundle["voucher_count"] == 2
    with transaction() as conn:
        assert services.sms_count(conn) == 0
        services.set_counted(conn, school["admin"], bundle["id"], 3000)
    with transaction() as conn:
        services.set_counted(conn, school["admin"], bundle["id"], 2000)
        with pytest.raises(DeskError):
            services.approve_all(conn, school["admin"], bundle["id"])
        still = services.get_voucher(conn, school["admin"], first["id"])
        assert still["status"] == "submitted"
        assert services.sms_count(conn) == 0
        rejected = services.reject_one(conn, school["admin"], first["id"], "Not in the cash")
    assert rejected["set_aside_paisa"] == 100000
    assert rejected["expected_paisa"] == 200000
    with transaction() as conn:
        services.approve_all(conn, school["admin"], bundle["id"])
        approved = services.get_voucher(conn, school["admin"], second["id"])
        sent_back = services.get_voucher(conn, school["admin"], first["id"])
        assert approved["status"] == "approved"
        assert sent_back["status"] == "rejected"
        assert services.sms_count(conn, second["id"]) == 1
        assert services.sms_count(conn, first["id"]) == 0
        ledger = services.get_ledger(conn, school["student"]["id"])
    assert ledger["paid_paisa"] == 200000
    assert ledger["remaining_paisa"] == 1000000


def test_last_single_approval_still_demands_a_match():
    school = _school()
    small = _pay(school["clerk"], school["student"]["id"], 1000)
    middle = _pay(school["clerk"], school["student"]["id"], 2000)
    large = _pay(school["clerk"], school["student"]["id"], 3000)
    bundle = _submit(school["clerk"])
    with transaction() as conn:
        services.set_counted(conn, school["admin"], bundle["id"], 1000)
        services.approve_one(conn, school["admin"], middle["id"])
        services.approve_one(conn, school["admin"], large["id"])
        with pytest.raises(DeskError):
            services.approve_one(conn, school["admin"], small["id"])
        assert services.get_voucher(conn, school["admin"], small["id"])["status"] == "submitted"
        assert services.sms_count(conn) == 2


def test_package_edits_do_not_rewrite_the_student_and_concession_is_principal_only():
    school = _school()
    with transaction() as conn:
        with pytest.raises(DeskError):
            services.set_concession(conn, school["clerk"], school["student"]["charges"][0]["id"], 500, "Brother")
        services.update_package(
            conn,
            school["admin"],
            school["package"]["id"],
            "Yearly",
            school["package"]["class_id"],
            school["package"]["academic_session_id"],
            [{"head_name": "Funds", "amount_rupees": 9999, "due_date": "2026-03-01"}],
        )
        ledger = services.get_ledger(conn, school["student"]["id"])
    assert ledger["total_paisa"] == 1200000
    with transaction() as conn:
        charge_id = services.get_ledger(conn, school["student"]["id"])["charges"][0]["id"]
        ledger = services.set_concession(conn, school["admin"], charge_id, 500, "Staff child")
    assert ledger["total_paisa"] == 1150000


def test_payment_sms_is_created_only_after_approval_and_test_mode_does_not_call_the_gateway(monkeypatch):
    def explode(*_args, **_kwargs):
        raise AssertionError("The SMS gateway was called in test mode.")

    monkeypatch.setattr("pics_fee.sms.deliver", explode)
    school = _school()
    voucher = _pay(school["clerk"], school["student"]["id"], 500)
    with transaction() as conn:
        assert services.sms_count(conn, voucher["id"]) == 0
    bundle = _submit(school["clerk"])
    with transaction() as conn:
        services.set_counted(conn, school["admin"], bundle["id"], 500)
        services.approve_all(conn, school["admin"], bundle["id"])
        messages = services.list_sms(conn)
    assert len(messages) == 1
    assert messages[0]["kind"] == "payment"
    assert messages[0]["status"] == "queued"
    assert messages[0]["phone"] == "923001234567"
    assert "Ali Raza" in messages[0]["body"]
    process_sms_queue(school["admin"])
    with transaction() as conn:
        sent = services.list_sms(conn)[0]
    assert sent["status"] == "sent"
    assert sent["provider_ref"] == "TEST-NOT-SENT"


def test_clerk_cannot_approve_and_reports_keep_waiting_cash_separate():
    school = _school()
    voucher = _pay(school["clerk"], school["student"]["id"], 400)
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    with transaction() as conn:
        with pytest.raises(DeskError):
            services.approve_all(conn, school["clerk"], 1)
        with pytest.raises(DeskError):
            services.record_payment(conn, school["admin"], school["student"]["id"], 100)
        report = services.report(conn, today, today)
    assert report["approved_count"] == 0
    assert report["waiting_count"] == 1
    assert report["outstanding_count"] == 1
    bundle = _submit(school["clerk"])
    with transaction() as conn:
        services.set_counted(conn, school["admin"], bundle["id"], 400)
        services.approve_all(conn, school["admin"], bundle["id"])
        report = services.report(conn, today, today)
        empty = services.report(conn, yesterday, yesterday)
        with pytest.raises(DeskError):
            services.delete_student(conn, school["clerk"], school["student"]["id"])
    assert report["approved_total_paisa"] == 40000
    assert report["student_count"] == 1
    assert empty["approved_count"] == 0
    assert voucher["voucher_no"].endswith("00001")


def test_voucher_and_handover_sheets_state_the_college_and_the_waiting_mark():
    school = _school()
    voucher = _pay(school["clerk"], school["student"]["id"], 700)
    html = voucher_html(voucher)
    assert COLLEGE_NAME in html
    assert "Waiting for principal approval" in html
    assert voucher["voucher_no"] in html
    bundle = _submit(school["clerk"])
    sheet = handover_html(bundle)
    assert "Cash handover" in sheet
    assert "Rs 700" in sheet


def test_api_roles_and_hidden_fingerprint():
    client = TestClient(create_app())
    health = client.get("/health")
    assert health.status_code == 200
    assert "fingerprint" not in health.json()
    assert health.json()["college"] == COLLEGE_NAME
    setup = client.post("/setup", json={"username": "principal", "password": "principal1", "display_name": "Principal"})
    assert setup.status_code == 200
    admin_token = setup.json()["token"]
    created = client.post(
        "/staff/clerks",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "clerk", "password": "clerkpass1", "display_name": "Clerk"},
    )
    assert created.status_code == 200
    clerk = client.post("/login", json={"username": "clerk", "password": "clerkpass1"})
    clerk_headers = {"Authorization": f"Bearer {clerk.json()['token']}"}
    forbidden = client.post("/payments/1/approve", headers=clerk_headers)
    assert forbidden.status_code == 403
    hidden = client.get("/sms/settings", headers=clerk_headers)
    assert hidden.status_code == 403
    assert client.get("/students").status_code == 401
    reset = client.post(
        "/local/reset-admin",
        json={"username": "principal", "password": "anotherpass1", "display_name": "Principal"},
    )
    assert reset.status_code == 403


def test_clerk_computer_cannot_become_the_principal(data_dir):
    from pics_fee.machine import MachineRoleError, ensure_machine_role, read_machine_role

    (data_dir / "fee.db").unlink()
    ensure_machine_role("clerk")
    with pytest.raises(MachineRoleError):
        ensure_machine_role("principal")
    assert read_machine_role() == "clerk"
    assert (data_dir / "machine.role").read_text(encoding="utf-8").strip() == "clerk"


def test_saved_clerk_connection_cannot_open_a_principal_desk(data_dir, monkeypatch):
    from pics_fee.client_api import save_clerk_config
    from pics_fee.machine import MachineRoleError, ensure_machine_role, read_machine_role

    monkeypatch.setenv("APPDATA", str(data_dir))
    (data_dir / "fee.db").unlink()
    save_clerk_config("192.168.1.20", "ab" * 32, 8765)
    with pytest.raises(MachineRoleError):
        ensure_machine_role("principal")
    assert read_machine_role() == "clerk"


def test_principal_computer_cannot_become_a_clerk_desk(data_dir, monkeypatch):
    from pics_fee.machine import MachineRoleError, ensure_machine_role, read_machine_role

    monkeypatch.setenv("APPDATA", str(data_dir / "roaming"))
    ensure_machine_role("principal")
    with pytest.raises(MachineRoleError):
        ensure_machine_role("clerk")
    assert read_machine_role() == "principal"


def test_wrong_password_is_remembered():
    _school()
    with transaction() as conn:
        with pytest.raises(DeskError):
            services.authenticate(conn, "principal", "wrong-password")
    with transaction() as conn:
        row = conn.execute("SELECT failed_attempts FROM users WHERE username = 'principal'").fetchone()
    assert row["failed_attempts"] == 1
