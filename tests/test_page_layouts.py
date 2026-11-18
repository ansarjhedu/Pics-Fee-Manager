"""Cash-waiting cards stay apart, and Records keeps a calendar on the left."""

import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QLabel

from pics_fee.ui.pages_desk import ApprovalPage
from pics_fee.ui.pages_records import RecordsPage
from pics_fee.ui.theme import apply_theme


class _Api:
    def __init__(self):
        self.paths: list[str] = []

    def request(self, method, path, body=None):
        self.paths.append(path)
        if path.startswith("/cash-waiting"):
            return {
                "ready_total_paisa": 500000,
                "with_clerk_total_paisa": 0,
                "ready_vouchers": 1,
                "with_clerk_count": 0,
                "with_clerk": [],
                "ready": [
                    {
                        "id": 3,
                        "clerk_name": "amir",
                        "submitted_at": "2026-11-15T12:32:00",
                        "expected_paisa": 500000,
                        "student_count": 1,
                        "counted_paisa": None,
                        "pending_paisa": 500000,
                        "status": "open",
                        "lines": [
                            {
                                "id": 9,
                                "voucher_no": "PICS-2026-00003",
                                "student_name": "test",
                                "class_name": "9th",
                                "amount_paisa": 500000,
                                "status": "submitted",
                                "status_label": "Waiting for principal approval",
                            }
                        ],
                    }
                ],
            }
        if path.startswith("/reports"):
            return {
                "approved_total_paisa": 1300000,
                "approved_count": 3,
                "student_count": 2,
                "outstanding_total_paisa": 2700000,
                "outstanding_count": 2,
                "waiting_total_paisa": 0,
                "waiting_count": 0,
                "payments": [
                    {
                        "id": 1,
                        "approved_at": "2026-11-15T07:49:00",
                        "voucher_no": "PICS-2026-00001",
                        "student_name": "test",
                        "class_name": "9th",
                        "amount_paisa": 500000,
                        "clerk_name": "amir",
                    }
                ],
                "outstanding": [
                    {
                        "student_id": 2,
                        "admission_no": "test from clerk",
                        "student_name": "test2",
                        "class_name": "9th",
                        "phone": "03113535489",
                        "remaining_paisa": 1700000,
                        "next_due": "2026-11-20",
                    }
                ],
            }
        if path.startswith("/classes"):
            return [{"id": 1, "name": "9th"}]
        return {}


def _box(host, widget) -> QRect:
    origin = widget.mapTo(host, widget.rect().topLeft())
    return QRect(origin, widget.size())


def test_handover_card_does_not_cover_the_count_heading():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    page = ApprovalPage(_Api(), None)
    page.resize(1180, 760)
    page.show()
    page.refresh()
    app.processEvents()
    card = page.students_value.parentWidget()
    caption = next(label for label in card.findChildren(QLabel) if label.text() == "Students")
    counted = next(label for label in page.findChildren(QLabel) if label.text() == "Counted cash")
    assert caption.geometry().bottom() < card.height() - 4
    assert _box(page, counted).top() >= _box(page, card).bottom() + 8
    assert "System total" in page.system_value.parentWidget().findChildren(QLabel)[-1].text() or any(
        label.text() == "System total" for label in page.system_value.parentWidget().findChildren(QLabel)
    )


def test_records_calendar_opens_from_the_top_and_lists_stay_apart():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    api = _Api()
    page = RecordsPage(api, None)
    page.resize(1280, 760)
    page.show()
    page.refresh()
    app.processEvents()
    assert page.calendar_panel.isHidden()
    page.calendar_button.click()
    app.processEvents()
    assert page.calendar_panel.isVisible()
    calendar_box = _box(page, page.month_board)
    vouchers = _box(page, page.payments)
    owing_title = _box(page, page.owing_title)
    owing = _box(page, page.owing)
    assert calendar_box.bottom() <= vouchers.top()
    assert owing_title.top() >= vouchers.bottom() + 8
    assert owing.top() >= owing_title.bottom()
    page._pick_day(date(2026, 11, 2))
    assert any("date_from=2026-11-02" in path for path in api.paths)
    assert page.showing.text() == "02 November 2026"
    assert page.calendar_panel.isVisible()
