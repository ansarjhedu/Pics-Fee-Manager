from __future__ import annotations

import calendar
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QSpinBox, QStackedWidget, QTableWidget, QWidget

from pics_fee.ui.dashboard import MonthBoard
from pics_fee.ui.theme import Page, block_title, button, card, day, fill_table, heading, mount_page, note, panel, rs, when


class RecordsPage(Page):
    def __init__(self, api, on_unauthorized):
        super().__init__(api, on_unauthorized)
        self._marks_loaded_for: tuple[int, int] | None = None
        root = mount_page(self)
        root.addWidget(heading("Records"))
        root.addWidget(note("Approved fee is the official total. Cash still waiting is shown apart from it."))
        controls_bar = panel("stat")
        controls = QHBoxLayout(controls_bar)
        controls.setSpacing(12)
        controls.setContentsMargins(14, 12, 14, 12)
        self.period = QComboBox()
        self.period.addItem("Day", "day")
        self.period.addItem("Month", "month")
        self.period.addItem("Year", "year")
        self.period.currentIndexChanged.connect(self._switch_period)
        self.day_label = QLabel(date.today().strftime("%d %b %Y"))
        self.day_label.setObjectName("blockTitle")
        self.day_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.day_label.setMinimumWidth(140)
        self.month_box = QComboBox()
        for number, name in enumerate(
            ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
            start=1,
        ):
            self.month_box.addItem(name, number)
        self.month_box.setCurrentIndex(date.today().month - 1)
        today = date.today()
        self.month_year = QSpinBox()
        self.year_box = QSpinBox()
        for box in (self.month_year, self.year_box):
            box.setRange(2000, 2100)
            box.setValue(today.year)
        self.period.setMaximumWidth(140)
        self.period_stack = QStackedWidget()
        self.period_stack.setMaximumWidth(360)
        self.period_stack.setMaximumHeight(44)
        self.period_stack.addWidget(self.day_label)
        self.period_stack.addWidget(_row(self.month_box, self.month_year))
        self.period_stack.addWidget(self.year_box)
        self.class_filter = QComboBox()
        self.class_filter.setMinimumWidth(150)
        self.class_filter.addItem("All classes", None)
        controls.addWidget(self.period)
        controls.addWidget(self.period_stack)
        controls.addWidget(self.class_filter)
        self.calendar_button = button("Calendar", "quiet")
        self.calendar_button.setCheckable(True)
        self.calendar_button.clicked.connect(self._toggle_calendar)
        controls.addWidget(self.calendar_button)
        show = button("Show records")
        show.clicked.connect(self.refresh)
        controls.addWidget(show)
        controls.addStretch(1)
        root.addWidget(controls_bar)
        self.calendar_panel = panel("stat")
        self.calendar_panel.setVisible(False)
        calendar_row = QHBoxLayout(self.calendar_panel)
        calendar_row.setContentsMargins(16, 14, 16, 14)
        calendar_row.setSpacing(18)
        self.month_board = MonthBoard(self._pick_day, self._shift_month)
        self.month_board.setFixedWidth(300)
        calendar_row.addWidget(self.month_board, 0, Qt.AlignmentFlag.AlignTop)
        calendar_row.addWidget(note("Select a day. The lists below follow that date."), 1)
        root.addWidget(self.calendar_panel)
        self.showing = QLabel("")
        self.showing.setObjectName("blockTitle")
        root.addWidget(self.showing)
        cards = QHBoxLayout()
        cards.setSpacing(12)
        cards.setContentsMargins(0, 0, 0, 0)
        approved, self.approved_value = card("Approved in this period", "Rs 0", "good")
        count, self.count_value = card("Vouchers", "0", "info")
        students, self.students_value = card("Students who paid", "0")
        outstanding, self.outstanding_value = card("Still outstanding", "Rs 0", "warn")
        waiting, self.waiting_value = card("Waiting", "Rs 0", "info")
        for widget in (approved, count, students, outstanding, waiting):
            cards.addWidget(widget)
        root.addLayout(cards)
        self.payments_title = block_title("Approved vouchers")
        root.addWidget(self.payments_title)
        self.payments = QTableWidget()
        root.addWidget(self.payments)
        self.owing_title = block_title("Students who still owe")
        root.addWidget(self.owing_title)
        self.owing = QTableWidget()
        root.addWidget(self.owing)
        self.class_filter.currentIndexChanged.connect(self.refresh)
        self.month_box.currentIndexChanged.connect(self._month_controls_changed)
        self.month_year.valueChanged.connect(self._month_controls_changed)
        self.year_box.valueChanged.connect(self._year_changed)

    def _switch_period(self) -> None:
        self.period_stack.setCurrentIndex(self.period.currentIndex())

    def _toggle_calendar(self) -> None:
        opened = self.calendar_button.isChecked()
        self.calendar_panel.setVisible(opened)
        self.calendar_button.setText("Hide calendar" if opened else "Calendar")

    def _pick_day(self, picked: date) -> None:
        self.month_board.selected = picked
        self.period.setCurrentIndex(self.period.findData("day"))
        self.month_box.blockSignals(True)
        self.month_year.blockSignals(True)
        self.month_box.setCurrentIndex(picked.month - 1)
        self.month_year.setValue(picked.year)
        self.month_box.blockSignals(False)
        self.month_year.blockSignals(False)
        self.day_label.setText(picked.strftime("%d %b %Y"))
        self.refresh()

    def _shift_month(self, cursor: date) -> None:
        self.month_box.blockSignals(True)
        self.month_year.blockSignals(True)
        self.month_box.setCurrentIndex(cursor.month - 1)
        self.month_year.setValue(cursor.year)
        self.month_box.blockSignals(False)
        self.month_year.blockSignals(False)
        self._marks_loaded_for = None
        self._load_marks()
        if self.period.currentData() == "month":
            self.refresh()

    def _month_controls_changed(self) -> None:
        year = self.month_year.value()
        month = self.month_box.currentData()
        if (self.month_board.cursor.year, self.month_board.cursor.month) != (year, month):
            self.month_board.show_month(year, month)
            self._marks_loaded_for = None
            self._load_marks()
        if self.period.currentData() == "month":
            self.refresh()

    def _year_changed(self) -> None:
        if self.period.currentData() == "year":
            self.refresh()

    def _range(self) -> tuple[str, str, str]:
        kind = self.period.currentData()
        picked = self.month_board.selected
        if kind == "day":
            text = picked.isoformat()
            title = picked.strftime("%d %B %Y")
            return text, text, title
        if kind == "month":
            year = self.month_year.value()
            month = self.month_box.currentData()
            last = calendar.monthrange(year, month)[1]
            title = date(year, month, 1).strftime("%B %Y")
            return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last:02d}", title
        year = self.year_box.value()
        return f"{year}-01-01", f"{year}-12-31", str(year)

    def _load_marks(self) -> None:
        cursor = self.month_board.cursor
        key = (cursor.year, cursor.month)
        if self._marks_loaded_for == key:
            return
        last = calendar.monthrange(cursor.year, cursor.month)[1]
        start = f"{cursor.year}-{cursor.month:02d}-01"
        end = f"{cursor.year}-{cursor.month:02d}-{last:02d}"
        report = self.call(lambda: self.api.request("GET", f"/reports?date_from={start}&date_to={end}"))
        if report is None:
            return
        marks: set[date] = set()
        for row in report.get("payments") or []:
            text = str(row.get("approved_at") or "")[:10]
            try:
                marks.add(date.fromisoformat(text))
            except ValueError:
                continue
        self._marks_loaded_for = key
        self.month_board.set_marks(marks)

    def refresh(self) -> None:
        start, end, title = self._range()
        self.day_label.setText(self.month_board.selected.strftime("%d %b %Y"))
        self.showing.setText(title)
        report = self.call(lambda: self.api.request("GET", f"/reports?date_from={start}&date_to={end}"))
        if report is None:
            return
        self.approved_value.setText(rs(report["approved_total_paisa"]))
        self.count_value.setText(str(report["approved_count"]))
        self.students_value.setText(str(report["student_count"]))
        self.outstanding_value.setText(f"{rs(report['outstanding_total_paisa'])}  ·  {report['outstanding_count']}")
        self.waiting_value.setText(f"{rs(report['waiting_total_paisa'])}  ·  {report['waiting_count']}")
        classes = self.call(lambda: self.api.request("GET", "/classes")) or []
        chosen = self.class_filter.currentData()
        self.class_filter.blockSignals(True)
        self.class_filter.clear()
        self.class_filter.addItem("All classes", None)
        for row in classes:
            self.class_filter.addItem(row["name"], row["name"])
        index = self.class_filter.findData(chosen)
        self.class_filter.setCurrentIndex(index if index >= 0 else 0)
        self.class_filter.blockSignals(False)
        class_name = self.class_filter.currentData()
        payments = report["payments"]
        owing = report["outstanding"]
        if class_name:
            payments = [row for row in payments if row["class_name"] == class_name]
            owing = [row for row in owing if row["class_name"] == class_name]
        fill_table(
            self.payments,
            ["When", "Voucher", "Student", "Class", "Amount", "Clerk"],
            [
                [when(row["approved_at"]), row["voucher_no"], row["student_name"], row["class_name"], rs(row["amount_paisa"]), row["clerk_name"]]
                for row in payments
            ],
            [row["id"] for row in payments],
            visible_rows=8,
            widths=[170, 160, 0, 90, 110, 120],
        )
        fill_table(
            self.owing,
            ["Admission", "Student", "Class", "Mobile", "Remaining", "Last date"],
            [
                [row["admission_no"], row["student_name"], row["class_name"], row["phone"], rs(row["remaining_paisa"]), day(row["next_due"])]
                for row in owing
            ],
            [row["student_id"] for row in owing],
            visible_rows=8,
            widths=[170, 0, 90, 140, 120, 120],
        )
        self._load_marks()


def _row(*widgets):
    holder = QWidget()
    layout = QHBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    for widget in widgets:
        layout.addWidget(widget)
    return holder
