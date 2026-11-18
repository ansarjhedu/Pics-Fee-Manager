"""Popups stay inside a 1366×768 desk and keep their actions readable."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLabel, QPushButton, QScrollArea

from pics_fee.ui.dialogs import (
    AdjustmentDialog,
    ClerkDialog,
    ConcessionDialog,
    FixVoucherDialog,
    NameDialog,
    PackageDialog,
    PasswordDialog,
    PaymentDialog,
    StudentDialog,
)
from pics_fee.ui.pages_classes import _EnrollDialog
from pics_fee.ui.pages_students import LedgerDialog, _PackageDialog
from pics_fee.ui.theme import apply_theme, dialog_limits, message_box

SCREEN_W, SCREEN_H = 1366, 768


class _Api:
    def __init__(self, payload):
        self.payload = payload

    def request(self, method, path, body=None):
        return self.payload


def _student():
    charges = [
        {
            "id": index,
            "head_name": f"Head {index}",
            "amount_paisa": 500000,
            "concession_paisa": 0,
            "due_date": "2026-12-01",
            "paid_paisa": 0,
            "remaining_paisa": 500000,
        }
        for index in range(1, 7)
    ]
    payments = [
        {
            "id": index,
            "voucher_no": f"PICS-2026-0000{index}",
            "amount_paisa": 100000,
            "status_label": "In the drawer",
            "created_at": "2026-11-15T09:00:00",
            "clerk_name": "Amir",
        }
        for index in range(1, 6)
    ]
    return {
        "id": 9,
        "name": "Test Student",
        "admission_no": "0311",
        "father_name": "Father Name",
        "class_id": 1,
        "class_name": "9th",
        "section": "A",
        "academic_session_id": 1,
        "session_name": "2026-2027",
        "phone": "03113535489",
        "status": "active",
        "next_due": "2026-12-01",
        "total_paisa": 2000000,
        "paid_paisa": 500000,
        "waiting_paisa": 500000,
        "remaining_paisa": 1500000,
        "collectable_paisa": 1000000,
        "charges": charges,
        "payments": payments,
        "adjustments": [{"id": 1, "created_at": "2026-11-15T09:00:00", "amount_paisa": -10000, "reason": "Opening balance"}],
    }


def _show(dialog):
    dialog.show()
    QApplication.processEvents()
    return dialog


def _inside(dialog, widget):
    top_left = widget.mapTo(dialog, widget.rect().topLeft())
    bottom_right = widget.mapTo(dialog, widget.rect().bottomRight())
    area = dialog.rect().adjusted(0, 0, 1, 1)
    assert area.contains(top_left), widget
    assert area.contains(bottom_right), (widget, bottom_right, dialog.size())


def _fits(dialog):
    max_w, max_h = dialog_limits()
    assert dialog.width() <= max_w
    assert dialog.height() <= max_h
    assert dialog.width() <= SCREEN_W - 40
    assert dialog.height() <= SCREEN_H - 40
    assert dialog.height() <= SCREEN_W


def test_clerk_popups_fit_the_desk_screen():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    student = _student()
    classes = [{"id": 1, "name": "9th"}]
    sessions = [{"id": 1, "name": "2026-2027"}]
    packages = [{"id": 3, "name": "Orphan quota", "class_id": 1, "academic_session_id": 1, "items": []}]
    dialogs = [
        LedgerDialog(None, _Api(student), None, "clerk", 9),
        StudentDialog(None, classes, sessions, packages, class_id=1, session_id=1, section="A"),
        StudentDialog(None, classes, sessions, packages, student={"admission_no": "0311", "name": "Test Student", "father_name": "Father Name", "section": "A", "phone": "03113535489", "class_id": 1, "academic_session_id": 1}),
        PaymentDialog(None, student),
        FixVoucherDialog(None, {"voucher_no": "PICS-2026-00001", "reject_reason": "The notes were short by Rs 500.", "amount_paisa": 500000}),
        _PackageDialog(None, packages),
        ClerkDialog(None),
        PasswordDialog(None, "New password for Amir"),
        NameDialog(None, "New class", "Class name"),
        ConcessionDialog(None, student["charges"][0] | {"concession_reason": ""}),
        AdjustmentDialog(None),
        PackageDialog(None, classes, sessions),
        _EnrollDialog(None, [{"id": 9, "admission_no": "0311", "name": "Test Student", "section": "A"}], "Orphan quota"),
    ]
    try:
        for dialog in dialogs:
            _show(dialog)
            _fits(dialog)
            buttons = dialog.findChildren(QPushButton)
            assert buttons, dialog.windowTitle()
            for widget in buttons:
                if widget.isVisible():
                    _inside(dialog, widget)
            for area in dialog.findChildren(QScrollArea):
                assert not area.horizontalScrollBar().isVisible(), dialog.windowTitle()
        ledger = dialogs[0]
        assert ledger.heading.text().startswith("Test Student")
        assert ledger.identity["class"].text() == "9th · A"
        assert ledger.identity["phone"].text() == "03113535489"
        assert any(button.text() == "Take payment" for button in ledger.findChildren(QPushButton))
        assert ledger.findChildren(QPushButton)[-1].text() in {button.text() for button in ledger.findChildren(QPushButton)}
        payment = dialogs[3]
        assert any(button.text() == "Save and print voucher" for button in payment.findChildren(QPushButton))
        assert "20,000" in payment.findChild(QLabel, "blockTitle").text() or any(
            "20,000" in label.text() or "Rs 20,000" in label.text() for label in payment.findChildren(QLabel)
        )
        box = message_box(None, __import__("PySide6.QtWidgets", fromlist=["QMessageBox"]).QMessageBox.Icon.Warning, "Hand these vouchers and the cash to the principal? You will not be able to change them after this.")
        _show(box)
        _fits(box)
        assert box.findChild(QDialogButtonBox) or box.findChildren(QPushButton)
    finally:
        for dialog in dialogs:
            dialog.close()
