from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTasks

from pics_fee.context import machine_var
from pics_fee.db import init_db, transaction
from pics_fee.errors import DeskError
from pics_fee.services import (
    add_adjustment,
    add_class,
    add_section,
    add_session,
    apply_package,
    approve_all,
    approve_one,
    authenticate,
    backup_info,
    cancel_payment,
    cash_overview,
    class_board,
    college_name,
    create_clerk,
    create_initial_admin,
    create_package,
    create_student,
    delete_class,
    delete_package,
    delete_section,
    delete_session,
    delete_student,
    desk_for,
    get_ledger,
    get_submission,
    get_voucher,
    is_initialized,
    list_audit,
    list_classes,
    list_clerks,
    list_open_submissions,
    list_packages,
    list_sessions,
    list_sms,
    list_students,
    logout,
    make_backup,
    open_session,
    queue_reminders,
    record_payment,
    reject_one,
    reminder_candidates,
    report,
    reset_admin_password,
    reset_clerk_password,
    revise_payment,
    save_sms_settings,
    set_clerk_active,
    set_concession,
    set_counted,
    set_student_status,
    sms_settings_view,
    submit_bundle,
    update_package,
    update_student,
    user_from_token,
)
from pics_fee.sms import process_sms_queue


def _work(fn):
    with transaction() as conn:
        return fn(conn)


def _queue_sms(background: BackgroundTasks, actor) -> None:
    background.add_task(process_sms_queue, actor, machine_var.get())


class SetupIn(BaseModel):
    username: str
    password: str
    display_name: str


class LoginIn(BaseModel):
    username: str
    password: str


class ClerkIn(BaseModel):
    username: str
    password: str
    display_name: str


class PasswordIn(BaseModel):
    password: str


class ActiveIn(BaseModel):
    active: bool


class NameIn(BaseModel):
    name: str


class PackageItemIn(BaseModel):
    head_name: str
    amount_rupees: int | float | str
    due_date: str


class PackageIn(BaseModel):
    name: str
    class_id: int
    academic_session_id: int
    items: list[PackageItemIn]


class StudentIn(BaseModel):
    admission_no: str
    name: str
    father_name: str
    class_id: int
    section: str = ""
    academic_session_id: int
    phone: str
    package_id: int | None = None


class StudentUpdateIn(BaseModel):
    admission_no: str
    name: str
    father_name: str
    class_id: int
    section: str = ""
    academic_session_id: int
    phone: str


class StatusIn(BaseModel):
    status: str


class PackageApplyIn(BaseModel):
    package_id: int


class ConcessionIn(BaseModel):
    amount_rupees: int | float | str
    reason: str


class AdjustmentIn(BaseModel):
    direction: str
    amount_rupees: int | float | str
    reason: str


class PaymentIn(BaseModel):
    student_id: int
    amount_rupees: int | float | str


class AmountIn(BaseModel):
    amount_rupees: int | float | str


class ReasonIn(BaseModel):
    reason: str


class SmsSettingsIn(BaseModel):
    test_mode: bool = True
    api_url: str = ""
    api_key: str = ""
    sender: str = ""
    payment_template: str
    reminder_template: str


class ReminderIn(BaseModel):
    student_ids: list[int] = Field(default_factory=list)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        init_db()
        try:
            ready = _work(is_initialized)
            if ready:
                make_backup()
        except Exception:
            pass
        yield

    app = FastAPI(title="PICS Fee Desk", lifespan=lifespan)

    @app.middleware("http")
    async def attach_machine(request: Request, call_next):
        token = machine_var.set((request.headers.get("x-machine-name") or "")[:80])
        try:
            return await call_next(request)
        finally:
            machine_var.reset(token)

    @app.exception_handler(DeskError)
    async def handle_desk(_request: Request, exc: DeskError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(sqlite3.IntegrityError)
    async def handle_integrity(_request: Request, _exc: sqlite3.IntegrityError):
        return JSONResponse(
            status_code=400,
            content={"detail": "That record conflicts with one already saved."},
        )

    def current_user(request: Request) -> dict:
        header = request.headers.get("authorization") or ""
        if not header.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Please sign in.")
        token = header.split(" ", 1)[1].strip()
        user = _work(lambda conn: user_from_token(conn, token))
        if not user:
            raise HTTPException(status_code=401, detail="Please sign in again.")
        user["_token"] = token
        return user

    def admin_user(user: dict = Depends(current_user)) -> dict:
        if user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Only the principal can do this.")
        return user

    @app.get("/health")
    def health():
        init_db()
        return _work(lambda conn: {"ok": True, "college": college_name(conn), "initialized": is_initialized(conn)})

    @app.post("/setup")
    def setup(body: SetupIn):
        def run(conn):
            user = create_initial_admin(conn, body.username, body.password, body.display_name)
            token = open_session(conn, user)
            return {"token": token, "user": user}

        return _work(run)

    @app.post("/login")
    def login(body: LoginIn):
        def run(conn):
            user = authenticate(conn, body.username, body.password)
            token = open_session(conn, user)
            return {"token": token, "user": user}

        return _work(run)

    @app.post("/logout")
    def sign_out(user: dict = Depends(current_user)):
        return _work(lambda conn: logout(conn, user["_token"], user) or {"ok": True})

    @app.get("/me")
    def me(user: dict = Depends(current_user)):
        return {key: value for key, value in user.items() if key != "_token"}

    @app.post("/local/reset-admin")
    def reset_admin(body: SetupIn, request: Request):
        host = request.client.host if request.client else ""
        if host not in {"127.0.0.1", "::1"}:
            raise HTTPException(
                status_code=403,
                detail="The principal password can be reset only on the principal's computer.",
            )
        _work(lambda conn: reset_admin_password(conn, body.username, body.password))
        return {"ok": True}

    @app.get("/staff/clerks")
    def clerks(_admin: dict = Depends(admin_user)):
        return _work(list_clerks)

    @app.post("/staff/clerks")
    def new_clerk(body: ClerkIn, admin: dict = Depends(admin_user)):
        return _work(lambda conn: create_clerk(conn, admin, body.username, body.password, body.display_name))

    @app.post("/staff/clerks/{user_id}/password")
    def clerk_password(user_id: int, body: PasswordIn, admin: dict = Depends(admin_user)):
        _work(lambda conn: reset_clerk_password(conn, admin, user_id, body.password))
        return {"ok": True}

    @app.post("/staff/clerks/{user_id}/active")
    def clerk_active(user_id: int, body: ActiveIn, admin: dict = Depends(admin_user)):
        return _work(lambda conn: set_clerk_active(conn, admin, user_id, body.active))

    @app.get("/audit")
    def audit_rows(username: str = "", limit: int = 200, _admin: dict = Depends(admin_user)):
        return _work(lambda conn: list_audit(conn, limit, username))

    @app.get("/classes")
    def classes(_user: dict = Depends(current_user)):
        return _work(list_classes)

    @app.get("/classes/board")
    def classes_board(
        session_id: int | None = None,
        status: str = "active",
        _user: dict = Depends(current_user),
    ):
        return _work(lambda conn: class_board(conn, session_id, status))

    @app.post("/classes/{class_id}/sections")
    def new_section(class_id: int, body: NameIn, admin: dict = Depends(admin_user)):
        return _work(lambda conn: add_section(conn, admin, class_id, body.name))

    @app.delete("/sections/{section_id}")
    def remove_section(section_id: int, admin: dict = Depends(admin_user)):
        _work(lambda conn: delete_section(conn, admin, section_id))
        return {"ok": True}

    @app.post("/classes")
    def new_class(body: NameIn, admin: dict = Depends(admin_user)):
        return _work(lambda conn: add_class(conn, admin, body.name))

    @app.delete("/classes/{class_id}")
    def remove_class(class_id: int, admin: dict = Depends(admin_user)):
        _work(lambda conn: delete_class(conn, admin, class_id))
        return {"ok": True}

    @app.get("/sessions")
    def sessions(_user: dict = Depends(current_user)):
        return _work(list_sessions)

    @app.post("/sessions")
    def new_session(body: NameIn, admin: dict = Depends(admin_user)):
        return _work(lambda conn: add_session(conn, admin, body.name))

    @app.delete("/sessions/{session_id}")
    def remove_session(session_id: int, admin: dict = Depends(admin_user)):
        _work(lambda conn: delete_session(conn, admin, session_id))
        return {"ok": True}

    @app.get("/packages")
    def packages(_user: dict = Depends(current_user)):
        return _work(list_packages)

    @app.post("/packages")
    def new_package(body: PackageIn, admin: dict = Depends(admin_user)):
        return _work(
            lambda conn: create_package(
                conn,
                admin,
                body.name,
                body.class_id,
                body.academic_session_id,
                [item.model_dump() for item in body.items],
            )
        )

    @app.put("/packages/{package_id}")
    def edit_package(package_id: int, body: PackageIn, admin: dict = Depends(admin_user)):
        return _work(
            lambda conn: update_package(
                conn,
                admin,
                package_id,
                body.name,
                body.class_id,
                body.academic_session_id,
                [item.model_dump() for item in body.items],
            )
        )

    @app.delete("/packages/{package_id}")
    def remove_package(package_id: int, admin: dict = Depends(admin_user)):
        _work(lambda conn: delete_package(conn, admin, package_id))
        return {"ok": True}

    @app.get("/students")
    def students(
        search: str = "",
        class_id: int | None = None,
        session_id: int | None = None,
        status: str = "active",
        _user: dict = Depends(current_user),
    ):
        return _work(lambda conn: list_students(conn, search, class_id, session_id, status))

    @app.post("/students")
    def new_student(body: StudentIn, user: dict = Depends(current_user)):
        return _work(lambda conn: create_student(conn, user, body.model_dump()))

    @app.get("/students/{student_id}")
    def student_ledger(student_id: int, _user: dict = Depends(current_user)):
        return _work(lambda conn: get_ledger(conn, student_id))

    @app.put("/students/{student_id}")
    def edit_student(student_id: int, body: StudentUpdateIn, user: dict = Depends(current_user)):
        return _work(lambda conn: update_student(conn, user, student_id, body.model_dump()))

    @app.delete("/students/{student_id}")
    def remove_student(student_id: int, user: dict = Depends(current_user)):
        _work(lambda conn: delete_student(conn, user, student_id))
        return {"ok": True}

    @app.post("/students/{student_id}/status")
    def student_status(student_id: int, body: StatusIn, user: dict = Depends(current_user)):
        return _work(lambda conn: set_student_status(conn, user, student_id, body.status))

    @app.post("/students/{student_id}/package")
    def student_package(student_id: int, body: PackageApplyIn, user: dict = Depends(current_user)):
        return _work(lambda conn: apply_package(conn, user, student_id, body.package_id))

    @app.post("/students/{student_id}/adjustments")
    def student_adjustment(student_id: int, body: AdjustmentIn, admin: dict = Depends(admin_user)):
        return _work(
            lambda conn: add_adjustment(conn, admin, student_id, body.direction, body.amount_rupees, body.reason)
        )

    @app.post("/charges/{charge_id}/concession")
    def concession(charge_id: int, body: ConcessionIn, admin: dict = Depends(admin_user)):
        return _work(lambda conn: set_concession(conn, admin, charge_id, body.amount_rupees, body.reason))

    @app.get("/desk")
    def desk(user: dict = Depends(current_user)):
        return _work(lambda conn: desk_for(conn, user))

    @app.post("/payments")
    def new_payment(body: PaymentIn, user: dict = Depends(current_user)):
        return _work(lambda conn: record_payment(conn, user, body.student_id, body.amount_rupees))

    @app.get("/payments/{payment_id}")
    def payment(payment_id: int, user: dict = Depends(current_user)):
        return _work(lambda conn: get_voucher(conn, user, payment_id))

    @app.post("/payments/{payment_id}/revise")
    def revise(payment_id: int, body: AmountIn, user: dict = Depends(current_user)):
        return _work(lambda conn: revise_payment(conn, user, payment_id, body.amount_rupees))

    @app.post("/payments/{payment_id}/cancel")
    def cancel(payment_id: int, user: dict = Depends(current_user)):
        return _work(lambda conn: cancel_payment(conn, user, payment_id))

    @app.post("/payments/{payment_id}/approve")
    def approve_payment(payment_id: int, background: BackgroundTasks, admin: dict = Depends(admin_user)):
        result = _work(lambda conn: approve_one(conn, admin, payment_id))
        _queue_sms(background, admin)
        return result

    @app.post("/payments/{payment_id}/reject")
    def reject_payment(payment_id: int, body: ReasonIn, admin: dict = Depends(admin_user)):
        return _work(lambda conn: reject_one(conn, admin, payment_id, body.reason))

    @app.post("/submissions")
    def submit(user: dict = Depends(current_user)):
        return _work(lambda conn: submit_bundle(conn, user))

    @app.get("/submissions/open")
    def open_submissions(_admin: dict = Depends(admin_user)):
        return _work(lambda conn: list_open_submissions(conn, _admin))

    @app.get("/cash-waiting")
    def cash_waiting(_admin: dict = Depends(admin_user)):
        return _work(lambda conn: cash_overview(conn, _admin))

    @app.get("/submissions/{submission_id}")
    def submission(submission_id: int, user: dict = Depends(current_user)):
        return _work(lambda conn: get_submission(conn, user, submission_id))

    @app.post("/submissions/{submission_id}/count")
    def count_cash(submission_id: int, body: AmountIn, admin: dict = Depends(admin_user)):
        return _work(lambda conn: set_counted(conn, admin, submission_id, body.amount_rupees))

    @app.post("/submissions/{submission_id}/approve-all")
    def approve_bundle(submission_id: int, background: BackgroundTasks, admin: dict = Depends(admin_user)):
        result = _work(lambda conn: approve_all(conn, admin, submission_id))
        _queue_sms(background, admin)
        return result

    @app.get("/reports")
    def reports(
        date_from: str = Query(...),
        date_to: str = Query(...),
        _user: dict = Depends(current_user),
    ):
        return _work(lambda conn: report(conn, date_from, date_to))

    @app.get("/sms/settings")
    def get_sms(_admin: dict = Depends(admin_user)):
        return _work(sms_settings_view)

    @app.put("/sms/settings")
    def put_sms(body: SmsSettingsIn, admin: dict = Depends(admin_user)):
        return _work(lambda conn: save_sms_settings(conn, admin, body.model_dump()))

    @app.get("/sms/reminders")
    def reminders(
        within_days: int = 7,
        include_all: bool = False,
        _admin: dict = Depends(admin_user),
    ):
        return _work(lambda conn: reminder_candidates(conn, within_days, include_all))

    @app.post("/sms/reminders")
    def send_reminders(body: ReminderIn, background: BackgroundTasks, admin: dict = Depends(admin_user)):
        count = _work(lambda conn: queue_reminders(conn, admin, body.student_ids))
        _queue_sms(background, admin)
        return {"queued": count}

    @app.get("/sms/log")
    def sms_log(_admin: dict = Depends(admin_user)):
        return _work(list_sms)

    @app.post("/sms/{message_id}/retry")
    def sms_retry(message_id: int, background: BackgroundTasks, admin: dict = Depends(admin_user)):
        _work(lambda conn: retry_sms_call(conn, admin, message_id))
        _queue_sms(background, admin)
        return {"ok": True}

    @app.get("/admin/info")
    def info(_admin: dict = Depends(admin_user)):
        return backup_info()

    @app.post("/admin/backup")
    def backup(admin: dict = Depends(admin_user)):
        path = make_backup(admin, manual=True)
        return {"path": path}

    @app.get("/admin/backup/download")
    def backup_download(admin: dict = Depends(admin_user)):
        path = make_backup(admin, manual=True)
        return FileResponse(path, filename="pics-fee-backup.db", media_type="application/octet-stream")

    return app


def retry_sms_call(conn, actor, message_id: int) -> None:
    from pics_fee.services import retry_sms

    retry_sms(conn, actor, message_id)
