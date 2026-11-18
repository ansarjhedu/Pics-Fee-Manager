from __future__ import annotations

import calendar
from datetime import date, timedelta
from urllib.parse import quote

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pics_fee.ui.theme import Page, block_title, button, card, rs


def _stamp(value) -> date | None:
    text = str(value or "")[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _tip_box(painter: QPainter, anchor: QPointF, bounds, title: str, detail: str) -> None:
    painter.setFont(QFont("Segoe UI", 9))
    width = max(painter.fontMetrics().horizontalAdvance(title), painter.fontMetrics().horizontalAdvance(detail)) + 28
    height = 52
    x = min(max(anchor.x() - width / 2, 4), bounds.width() - width - 4)
    y = max(anchor.y() - height - 12, 4)
    rect = QRectF(x, y, width, height)
    painter.setPen(QPen(QColor("#e6eeea"), 1))
    painter.setBrush(QColor("#ffffff"))
    painter.drawRoundedRect(rect, 10, 10)
    painter.setPen(QColor("#24312c"))
    painter.drawText(QRectF(x + 12, y + 6, width - 20, 18), Qt.AlignmentFlag.AlignLeft, title)
    painter.setPen(QColor("#12a150"))
    painter.drawText(QRectF(x + 12, y + 26, width - 20, 18), Qt.AlignmentFlag.AlignLeft, detail)


class BarChart(QWidget):
    def __init__(self):
        super().__init__()
        self._labels: list[str] = []
        self._values: list[float] = []
        self._hover: int | None = None
        self._plot = QRectF()
        self._gap = 1.0
        self.setMouseTracking(True)
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_values(self, labels: list[str], values: list[float]) -> None:
        self._labels = labels
        self._values = [float(item) for item in values]
        self._hover = None
        self.update()

    def leaveEvent(self, _event) -> None:
        self._hover = None
        self.update()

    def mouseMoveEvent(self, event) -> None:
        labels = self._labels or ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        gap = self._gap or 1
        index = int((event.position().x() - self._plot.left()) / gap)
        hover = index if 0 <= index < len(labels) else None
        if hover != self._hover:
            self._hover = hover
            self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        labels = self._labels or ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        values = self._values or [0.0] * len(labels)
        peak = max(values) if any(values) else 1
        left, top, right, bottom = 36, 16, 12, 28
        plot = QRectF(left, top, max(self.width() - left - right, 10), max(self.height() - top - bottom, 10))
        self._plot = plot
        gap = plot.width() / max(len(labels), 1)
        self._gap = gap
        painter.setPen(QPen(QColor("#e6eeea"), 1))
        for step in range(4):
            y = plot.top() + plot.height() * step / 3
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
        painter.setFont(QFont("Segoe UI", 8))
        bar_width = min(28, gap * 0.45)
        anchor = None
        for index, label in enumerate(labels):
            height = 0 if peak == 0 else plot.height() * (values[index] / peak)
            x = plot.left() + gap * index + (gap - bar_width) / 2
            y = plot.bottom() - height
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#0e8a43" if index == self._hover else "#12a150"))
            painter.drawRoundedRect(QRectF(x, y, bar_width, max(height, 0)), 6, 6)
            painter.setPen(QColor("#8b938e"))
            painter.drawText(QRectF(plot.left() + gap * index, plot.bottom() + 4, gap, 20), Qt.AlignmentFlag.AlignHCenter, label)
            if index == self._hover:
                anchor = QPointF(x + bar_width / 2, y)
        if anchor is not None and self._hover is not None:
            _tip_box(painter, anchor, self.rect(), labels[self._hover], rs(int(round(values[self._hover] * 100))))
        painter.end()


class LineChart(QWidget):
    def __init__(self):
        super().__init__()
        self._labels: list[str] = []
        self._values: list[float] = []
        self._points: list[QPointF] = []
        self._hover: int | None = None
        self.setMouseTracking(True)
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_values(self, labels: list[str], values: list[float]) -> None:
        self._labels = labels
        self._values = [float(item) for item in values]
        self._hover = None
        self.update()

    def leaveEvent(self, _event) -> None:
        self._hover = None
        self.update()

    def mouseMoveEvent(self, event) -> None:
        hover = None
        best = 28.0
        for index, point in enumerate(self._points):
            distance = (point - event.position()).manhattanLength()
            if distance < best:
                best = distance
                hover = index
        if hover != self._hover:
            self._hover = hover
            self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        labels = self._labels or ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
        values = self._values or [0.0] * len(labels)
        peak = max(values) if any(values) else 1
        left, top, right, bottom = 44, 16, 12, 28
        plot = QRectF(left, top, max(self.width() - left - right, 10), max(self.height() - top - bottom, 10))
        painter.setPen(QPen(QColor("#e6eeea"), 1))
        for step in range(4):
            y = plot.top() + plot.height() * step / 3
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
        points = []
        span = max(len(labels) - 1, 1)
        for index, value in enumerate(values):
            x = plot.left() + plot.width() * index / span
            y = plot.bottom() - plot.height() * (value / peak)
            points.append(QPointF(x, y))
        self._points = points
        painter.setPen(QPen(QColor("#e0a100"), 2.4))
        for start, end in zip(points, points[1:]):
            painter.drawLine(start, end)
        painter.setPen(Qt.PenStyle.NoPen)
        for index, point in enumerate(points):
            painter.setBrush(QColor("#12a150") if index == self._hover else QColor("#e0a100"))
            painter.drawEllipse(point, 7 if index == self._hover else 4, 7 if index == self._hover else 4)
        painter.setPen(QColor("#8b938e"))
        painter.setFont(QFont("Segoe UI", 8))
        for index, label in enumerate(labels):
            x = plot.left() + plot.width() * index / span
            painter.drawText(QRectF(x - 24, plot.bottom() + 4, 48, 20), Qt.AlignmentFlag.AlignHCenter, label)
        if self._hover is not None and self._hover < len(points):
            _tip_box(painter, points[self._hover], self.rect(), labels[self._hover], rs(int(round(values[self._hover] * 100))))
        painter.end()


class MonthBoard(QWidget):
    def __init__(self, on_pick, on_shift=None):
        super().__init__()
        self._on_pick = on_pick
        self._on_shift = on_shift
        self.cursor = date.today().replace(day=1)
        self.selected = date.today()
        self.marks: set[date] = set()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        header = QHBoxLayout()
        self.title = QLabel()
        self.title.setObjectName("blockTitle")
        previous = button("<", "quiet")
        following = button(">", "quiet")
        previous.clicked.connect(self._previous)
        following.clicked.connect(self._next)
        header.addWidget(self.title, 1)
        header.addWidget(previous)
        header.addWidget(following)
        root.addLayout(header)
        names = QHBoxLayout()
        for name in ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"):
            label = QLabel(name)
            label.setObjectName("muted")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            names.addWidget(label)
        root.addLayout(names)
        self.grid = QGridLayout()
        self.grid.setSpacing(4)
        root.addLayout(self.grid)
        self._cells: list[QPushButton] = []
        self._draw()

    def set_marks(self, marks: set[date]) -> None:
        self.marks = marks
        self._draw()

    def _previous(self) -> None:
        year, month = self.cursor.year, self.cursor.month - 1
        if month == 0:
            year, month = year - 1, 12
        self.cursor = date(year, month, 1)
        self._draw()
        if self._on_shift:
            self._on_shift(self.cursor)

    def show_month(self, year: int, month: int) -> None:
        self.cursor = date(year, month, 1)
        self._draw()

    def _next(self) -> None:
        year, month = self.cursor.year, self.cursor.month + 1
        if month == 13:
            year, month = year + 1, 1
        self.cursor = date(year, month, 1)
        self._draw()
        if self._on_shift:
            self._on_shift(self.cursor)

    def _draw(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cells.clear()
        shown = self.selected if (self.selected.year, self.selected.month) == (self.cursor.year, self.cursor.month) else self.cursor
        self.title.setText(f"{self.cursor.strftime('%B')}, {shown.day} {shown.strftime('%A')}")
        start = (self.cursor.weekday() + 1) % 7
        count = calendar.monthrange(self.cursor.year, self.cursor.month)[1]
        for index in range(42):
            day_number = index - start + 1
            cell = button("", "day")
            cell.setCheckable(True)
            cell.setFixedSize(36, 36)
            if 1 <= day_number <= count:
                shown = date(self.cursor.year, self.cursor.month, day_number)
                cell.setText(str(day_number))
                cell.setChecked(shown == self.selected)
                if shown in self.marks and shown != self.selected:
                    cell.setStyleSheet("color: #12a150; font-weight: 700;")
                cell.clicked.connect(lambda _checked=False, picked=shown: self._pick(picked))
            else:
                cell.setEnabled(False)
            self.grid.addWidget(cell, index // 7, index % 7)
            self._cells.append(cell)

    def _pick(self, picked: date) -> None:
        self.selected = picked
        QTimer.singleShot(0, self._draw)
        self._on_pick(picked)


def _row(color: str, initial: str, title: str, detail: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("stat")
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(10, 8, 10, 8)
    badge = QLabel(initial[:1].upper())
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setFixedSize(36, 36)
    badge.setStyleSheet(f"background: {color}; color: white; border-radius: 18px; font-weight: 700;")
    text = QVBoxLayout()
    text.setSpacing(0)
    name = QLabel(title)
    name.setObjectName("blockTitle")
    extra = QLabel(detail)
    extra.setObjectName("muted")
    text.addWidget(name)
    text.addWidget(extra)
    layout.addWidget(badge)
    layout.addLayout(text, 1)
    return frame


class OverviewPage(Page):
    """Home screen laid out as a dashboard: cards, charts, and a calendar rail."""

    def __init__(self, api, on_unauthorized, role: str, on_open):
        super().__init__(api, on_unauthorized)
        self.role = role
        self.on_open = on_open
        self._payments: list[dict] = []
        self._items: list[tuple[str, str, str]] = []
        body = QHBoxLayout(self)
        body.setContentsMargins(16, 6, 8, 12)
        body.setSpacing(8)
        scroll = QScrollArea()
        scroll.setObjectName("pageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        main = QVBoxLayout(inner)
        main.setContentsMargins(8, 8, 12, 16)
        main.setSpacing(14)
        welcome = QLabel("Welcome back. Here is the fee desk today.")
        welcome.setObjectName("muted")
        main.addWidget(welcome)
        tabs = QHBoxLayout()
        tabs.setSpacing(4)
        current = button("Overview", "tab")
        current.setCheckable(True)
        current.setChecked(True)
        tabs.addWidget(current)
        names = (
            ["Cash waiting", "Classes", "Fees", "Clerks", "Records", "Messages"]
            if role == "admin"
            else ["Desk", "Classes", "Records"]
        )
        for name in names:
            link = button(name, "tab")
            link.clicked.connect(lambda _checked=False, target=name: self.on_open(target))
            tabs.addWidget(link)
        tabs.addStretch(1)
        main.addLayout(tabs)

        captions = (
            [
                ("Students on roll", "good"),
                ("Collected this month", "good"),
                ("Still outstanding", "warn"),
                ("Still with the clerk", "warn"),
                ("Ready to count", "info"),
                ("Vouchers waiting", "info"),
            ]
            if role == "admin"
            else [
                ("In your drawer", "warn"),
                ("Handed over", "info"),
                ("Sent back", "warn"),
                ("Students on roll", "good"),
                ("Collected this month", "good"),
                ("Still outstanding", "warn"),
            ]
        )
        self.values: list[QLabel] = []
        grid = QGridLayout()
        grid.setSpacing(12)
        for index, (caption, tone) in enumerate(captions):
            frame, value = card(caption, "—", tone)
            self.values.append(value)
            grid.addWidget(frame, index // 3, index % 3)
        main.addLayout(grid)

        charts = QHBoxLayout()
        charts.setSpacing(12)
        week_card = QFrame()
        week_card.setObjectName("stat")
        week_layout = QVBoxLayout(week_card)
        week_layout.setContentsMargins(16, 14, 16, 12)
        week_layout.addWidget(block_title("Fees collected this week"))
        self.week = BarChart()
        week_layout.addWidget(self.week)
        month_card = QFrame()
        month_card.setObjectName("stat")
        month_layout = QVBoxLayout(month_card)
        month_layout.setContentsMargins(16, 14, 16, 12)
        month_layout.addWidget(block_title("Monthly fees collected"))
        self.months = LineChart()
        month_layout.addWidget(self.months)
        charts.addWidget(week_card, 1)
        charts.addWidget(month_card, 1)
        main.addLayout(charts)

        lower = QHBoxLayout()
        lower.setSpacing(12)
        self.banner = QFrame()
        self.banner.setObjectName("banner")
        banner_layout = QVBoxLayout(self.banner)
        banner_layout.setContentsMargins(18, 16, 18, 16)
        banner_layout.setSpacing(8)
        banner_title = QLabel("Cash waiting" if role == "admin" else "In the drawer")
        banner_title.setObjectName("blockTitle")
        self.banner_note = QLabel("Recorded notes that still need a handover.")
        banner_layout.addWidget(banner_title)
        banner_layout.addWidget(self.banner_note)
        chips = QHBoxLayout()
        self.left_chip = button("With the clerk", "chip")
        self.right_chip = button("Ready to count", "chip")
        target = "Cash waiting" if role == "admin" else "Desk"
        self.left_chip.clicked.connect(lambda: self.on_open(target))
        self.right_chip.clicked.connect(lambda: self.on_open(target))
        chips.addWidget(self.left_chip)
        chips.addWidget(self.right_chip)
        chips.addStretch(1)
        banner_layout.addLayout(chips)
        banner_layout.addStretch(1)
        lower.addWidget(self.banner, 1)

        events = QFrame()
        events.setObjectName("stat")
        events_layout = QVBoxLayout(events)
        events_layout.setContentsMargins(16, 14, 16, 14)
        events_head = QHBoxLayout()
        events_head.addWidget(block_title("Open handovers"))
        events_head.addStretch(1)
        open_page = button("Open", "quiet")
        open_page.clicked.connect(lambda: self.on_open(target))
        events_head.addWidget(open_page)
        events_layout.addLayout(events_head)
        self.events = QVBoxLayout()
        self.events.setSpacing(8)
        events_layout.addLayout(self.events)
        events_layout.addStretch(1)
        lower.addWidget(events, 1)
        main.addLayout(lower)
        main.addStretch(1)
        scroll.setWidget(inner)
        body.addWidget(scroll, 1)

        rail_host = QFrame()
        rail_host.setObjectName("rail")
        rail_host.setFixedWidth(300)
        rail = QVBoxLayout(rail_host)
        rail.setContentsMargins(12, 12, 12, 12)
        rail.setSpacing(12)
        self.month_board = MonthBoard(self._show_day)
        rail.addWidget(self.month_board)
        rail.addWidget(block_title("Today's collections"))
        self.schedule_title = QLabel("")
        self.schedule_title.setObjectName("muted")
        rail.addWidget(self.schedule_title)
        self.schedule = QVBoxLayout()
        self.schedule.setSpacing(8)
        rail.addLayout(self.schedule)
        rail.addStretch(1)
        body.addWidget(rail_host)

    def refresh(self) -> None:
        today = date.today()
        report = self.call(
            lambda: self.api.request(
                "GET",
                f"/reports?date_from={date(today.year, 1, 1).isoformat()}&date_to={today.isoformat()}",
            )
        )
        students = self.call(lambda: self.api.request("GET", "/students?status=active"))
        self._payments = (report or {}).get("payments", [])
        marks = {day for item in self._payments if (day := _stamp(item.get("approved_at")))}
        self.month_board.set_marks(marks)
        month_total = sum(item["amount_paisa"] for item in self._payments if _stamp(item.get("approved_at")) and _stamp(item.get("approved_at")).month == today.month)
        student_count = len(students or [])
        outstanding = rs((report or {}).get("outstanding_total_paisa", 0))
        if self.role == "admin":
            cash = self.call(lambda: self.api.request("GET", "/cash-waiting")) or {}
            figures = [
                str(student_count),
                rs(month_total),
                outstanding,
                rs(cash.get("with_clerk_total_paisa", 0)),
                rs(cash.get("ready_total_paisa", 0)),
                str(int(cash.get("with_clerk_count", 0)) + int(cash.get("ready_vouchers", 0))),
            ]
            self.left_chip.setText(f"With the clerk  {cash.get('with_clerk_count', 0)}")
            self.right_chip.setText(f"Ready to count  {cash.get('ready_vouchers', 0)}")
            self._items = [
                ("#12a150", item.get("clerk_name") or "Handover", f"{item.get('voucher_count', 0)} vouchers", rs(item.get("expected_paisa", 0)))
                for item in cash.get("ready") or []
            ]
        else:
            desk = self.call(lambda: self.api.request("GET", "/desk")) or {}
            drawer = desk.get("unsubmitted") or {}
            handed = desk.get("submitted") or {}
            sent = desk.get("rejected") or {}
            figures = [
                rs(drawer.get("total_paisa", 0)),
                rs(handed.get("total_paisa", 0)),
                rs(sent.get("total_paisa", 0)),
                str(student_count),
                rs(month_total),
                outstanding,
            ]
            self.left_chip.setText(f"In the drawer  {drawer.get('count', 0)}")
            self.right_chip.setText(f"Handed over  {handed.get('count', 0)}")
            self._items = [
                ("#12a150", "Handover", f"{item.get('voucher_count', 0)} vouchers", rs(item.get("expected_paisa", 0)))
                for item in desk.get("open_submissions") or []
            ]
        for label, figure in zip(self.values, figures):
            label.setText(figure)
        self._fill_charts(today)
        self._fill_events()
        self._show_day(self.month_board.selected)

    def _fill_charts(self, today: date) -> None:
        monday = today - timedelta(days=today.weekday())
        days = [monday + timedelta(days=offset) for offset in range(7)]
        week_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        week_values = []
        for day in days:
            week_values.append(sum(item["amount_paisa"] for item in self._payments if _stamp(item.get("approved_at")) == day) / 100)
        self.week.set_values(week_labels, week_values)
        months = []
        cursor = date(today.year, today.month, 1)
        for _ in range(5):
            month = cursor.month - 1
            year = cursor.year
            if month == 0:
                month, year = 12, year - 1
            cursor = date(year, month, 1)
            months.append(cursor)
        months.reverse()
        months.append(date(today.year, today.month, 1))
        labels = [item.strftime("%b") for item in months]
        values = []
        for item in months:
            values.append(
                sum(
                    payment["amount_paisa"]
                    for payment in self._payments
                    if (paid := _stamp(payment.get("approved_at"))) and paid.year == item.year and paid.month == item.month
                )
                / 100
            )
        self.months.set_values(labels, values)

    def _fill_events(self) -> None:
        while self.events.count():
            item = self.events.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not self._items:
            empty = QLabel("No handover is open.")
            empty.setObjectName("muted")
            self.events.addWidget(empty)
            return
        for color, title, detail, amount in self._items[:4]:
            self.events.addWidget(_row(color, title, f"{title} · {amount}", detail))

    def _show_day(self, picked: date) -> None:
        self.schedule_title.setText(picked.strftime("%d %B %Y"))
        while self.schedule.count():
            item = self.schedule.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        rows = [item for item in self._payments if _stamp(item.get("approved_at")) == picked]
        if not rows:
            empty = QLabel("No fee was approved on this day.")
            empty.setObjectName("muted")
            empty.setWordWrap(True)
            self.schedule.addWidget(empty)
            return
        colors = ["#12a150", "#e0a100", "#e25b73", "#3d8bfd"]
        for index, item in enumerate(rows[:6]):
            self.schedule.addWidget(
                _row(colors[index % len(colors)], item.get("student_name") or "S", item.get("student_name") or "Student", f"{item.get('class_name', '')}  ·  {rs(item.get('amount_paisa', 0))}")
            )


def search_students(api, text: str):
    return api.request("GET", f"/students?search={quote(text)}&status=active")
