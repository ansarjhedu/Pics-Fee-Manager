from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pics_fee.client_api import ApiError
from pics_fee.errors import DeskError
from pics_fee.textfmt import format_date, format_rs, format_when

LIGHT = """
QWidget { background: transparent; color: #1c2140; font-size: 14px; }
QWidget#appRoot { background: #e7eeea; }
QLabel { background: transparent; }
QLabel#headerTitle { font-size: 16px; font-weight: 700; color: #1c2140; }
QLabel#headerMeta { color: #6d7390; font-size: 13px; }
QLabel#section { font-size: 18px; font-weight: 700; color: #1c2140; }
QLabel#blockTitle { font-size: 15px; font-weight: 700; color: #1c2140; }
QLabel#muted { color: #6d7390; }
QLabel#eyebrow { color: #6d7390; font-size: 12px; font-weight: 700; }
QLabel#money { font-size: 22px; font-weight: 700; color: #1c2140; }
QLabel#good { color: #157a45; font-size: 14px; font-weight: 700; }
QLabel#bad { color: #c43b55; font-size: 14px; font-weight: 700; }
QFrame#shell { background: #ffffff; border: 1px solid #e3ebe6; border-radius: 22px; }
QFrame#header {
    background: #ffffff;
    border: none;
    border-bottom: 1px solid #eef2f0;
}
QFrame#nav {
    background: #ffffff;
    border: none;
    border-right: 1px solid #eef2f0;
}
QFrame#rail { background: #ffffff; border: none; }
QFrame#glass, QFrame#card, QFrame#stat {
    background: #ffffff;
    border: 1px solid #e6eeea;
    border-radius: 16px;
}
QFrame#notice {
    background: #fff6e4;
    border: 1px solid #f0d7a2;
    border-radius: 16px;
}
QPushButton {
    background: #12a150; color: white; border: none; border-radius: 12px;
    padding: 10px 16px; font-weight: 600;
}
QPushButton:hover { background: #0e8a43; }
QPushButton:disabled { background: #d9dce8; color: #7b8198; }
QPushButton[kind="quiet"] {
    background: #ffffff; color: #0f7a45;
    border: 1px solid #d7efe4;
}
QPushButton[kind="quiet"]:hover { background: #f3faf6; }
QPushButton[kind="danger"] { background: #d4536a; }
QPushButton[kind="danger"]:hover { background: #c0435a; }
QPushButton[kind="nav"] {
    background: transparent; color: #3d4a44; text-align: left;
    padding: 10px 14px; border-radius: 18px; font-weight: 600;
    border: 1px solid transparent;
}
QPushButton[kind="nav"]:hover { background: #f3faf6; }
QPushButton[kind="nav"]:checked { background: #12a150; color: white; border: none; }
QPushButton[kind="tab"] {
    background: transparent; color: #8b938e; border: none; border-radius: 0;
    border-bottom: 2px solid transparent; padding: 8px 14px; font-weight: 700;
}
QPushButton[kind="tab"]:hover { color: #12a150; background: transparent; }
QPushButton[kind="tab"]:checked { color: #12a150; border-bottom: 2px solid #12a150; background: transparent; }
QPushButton[kind="day"] {
    background: transparent; color: #24312c; border: none; border-radius: 16px;
    padding: 0; min-width: 32px; min-height: 32px; font-weight: 600;
}
QPushButton[kind="day"]:hover { background: #e7f6ee; }
QPushButton[kind="day"]:checked { background: #12a150; color: white; }
QPushButton[kind="chip"] {
    background: rgba(255,255,255,0.18); color: white; border: none; border-radius: 14px;
    padding: 8px 12px; font-weight: 600;
}
QPushButton[kind="chip"]:hover { background: rgba(255,255,255,0.28); }
QFrame#banner { background: #14915f; border: none; border-radius: 18px; }
QFrame#banner QLabel { color: white; background: transparent; }
QLineEdit#search {
    background: #f3f6f4; border: 1px solid #e6eeea; border-radius: 18px; padding: 8px 16px;
}
QLineEdit, QComboBox, QDateEdit, QSpinBox {
    background: #f5f6fb;
    border: 1px solid #e4e6f0;
    border-radius: 10px;
    padding: 8px 12px;
    min-height: 18px;
    max-height: 40px;
    color: #1c2140;
    selection-background-color: #12a150;
    selection-color: white;
}
QPlainTextEdit, QListWidget {
    background: #ffffff;
    border: 1px solid #e4e6f0;
    border-radius: 12px;
    padding: 8px 12px;
    color: #1c2140;
    selection-background-color: #e7f6ee;
    selection-color: #1c2140;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QPlainTextEdit:focus, QListWidget:focus {
    border: 1px solid #12a150;
    background: white;
}
QListWidget::item { padding: 8px 8px; border-radius: 8px; }
QListWidget::item:selected { background: #e7f6ee; color: #1c2140; }
QTableWidget {
    background: #ffffff;
    alternate-background-color: #f7faf8;
    border: 1px solid #eceef5;
    border-radius: 14px;
    gridline-color: #f0f1f6;
    selection-background-color: #e7f6ee;
    selection-color: #1c2140;
}
QTableWidget::item { padding: 6px 8px; }
QHeaderView::section {
    background: #f7f8fc;
    color: #8b90a5;
    padding: 10px 8px;
    border: none;
    border-bottom: 1px solid #eceef5;
    font-weight: 700;
    font-size: 12px;
}
QCheckBox { background: transparent; spacing: 8px; }
QScrollArea { border: none; background: transparent; }
QScrollArea#pageScroll { background: transparent; }
QWidget#page { background: transparent; }
QDialog, QMessageBox { background: #f6f7fb; }
QDialog QLabel, QMessageBox QLabel { color: #1c2140; }
"""

DARK = """
QWidget { background: transparent; color: #f3f4fb; font-size: 14px; }
QWidget#appRoot { background: #121816; }
QLabel { background: transparent; color: #f3f4fb; }
QLabel#headerTitle { font-size: 16px; font-weight: 700; color: white; }
QLabel#headerMeta { color: #c5c9da; font-size: 13px; }
QLabel#section { font-size: 18px; font-weight: 700; color: white; }
QLabel#blockTitle { font-size: 15px; font-weight: 700; color: white; }
QLabel#muted { color: #b7bdd0; }
QLabel#eyebrow { color: #b7bdd0; font-size: 12px; font-weight: 700; }
QLabel#money { font-size: 22px; font-weight: 700; color: white; }
QLabel#good { color: #7ddeaf; font-size: 14px; font-weight: 700; }
QLabel#bad { color: #ffb3c0; font-size: 14px; font-weight: 700; }
QFrame#shell { background: #1a211e; border: 1px solid rgba(255,255,255,0.06); border-radius: 22px; }
QFrame#header {
    background: #1a211e;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
QFrame#nav {
    background: #1a211e;
    border: none;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
}
QFrame#rail { background: #1a211e; border: none; }
QFrame#glass, QFrame#card, QFrame#stat {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 16px;
}
QFrame#notice {
    background: rgba(240, 180, 80, 0.16);
    border: 1px solid rgba(240, 180, 80, 0.35);
    border-radius: 16px;
}
QPushButton {
    background: #1aaa62; color: white; border: none; border-radius: 12px;
    padding: 10px 16px; font-weight: 600;
}
QPushButton:hover { background: #12a150; }
QPushButton:disabled { background: rgba(255,255,255,0.12); color: #9aa0b8; }
QPushButton[kind="quiet"] {
    background: rgba(255,255,255,0.08); color: #b7f0d0;
    border: 1px solid rgba(255,255,255,0.16);
}
QPushButton[kind="quiet"]:hover { background: rgba(255,255,255,0.14); }
QPushButton[kind="danger"] { background: #d4536a; }
QPushButton[kind="danger"]:hover { background: #e2647a; }
QPushButton[kind="nav"] {
    background: transparent; color: #e6e8f4; text-align: left;
    padding: 10px 14px; border-radius: 18px; font-weight: 600;
    border: 1px solid transparent;
}
QPushButton[kind="nav"]:hover { background: rgba(255,255,255,0.06); }
QPushButton[kind="nav"]:checked { background: #12a150; color: white; border: none; }
QPushButton[kind="tab"] {
    background: transparent; color: #b7bdd0; border: none; border-radius: 0;
    border-bottom: 2px solid transparent; padding: 8px 14px; font-weight: 700;
}
QPushButton[kind="tab"]:checked { color: #7ddeaf; border-bottom: 2px solid #1aaa62; background: transparent; }
QPushButton[kind="day"] {
    background: transparent; color: #f3f4fb; border: none; border-radius: 16px;
    padding: 0; min-width: 32px; min-height: 32px; font-weight: 600;
}
QPushButton[kind="day"]:checked { background: #12a150; color: white; }
QPushButton[kind="chip"] {
    background: rgba(255,255,255,0.18); color: white; border: none; border-radius: 14px; padding: 8px 12px;
}
QFrame#banner { background: #14915f; border: none; border-radius: 18px; }
QFrame#banner QLabel { color: white; background: transparent; }
QLineEdit#search {
    background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.10); border-radius: 18px; padding: 8px 16px;
}
QLineEdit, QComboBox, QDateEdit, QSpinBox {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 10px;
    padding: 8px 12px;
    min-height: 18px;
    max-height: 40px;
    color: #f3f4fb;
    selection-background-color: #12a150;
    selection-color: white;
}
QPlainTextEdit, QListWidget {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 12px;
    padding: 8px 12px;
    color: #f3f4fb;
    selection-background-color: rgba(108, 77, 255, 0.45);
    selection-color: white;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QPlainTextEdit:focus, QListWidget:focus {
    border: 1px solid #1aaa62;
}
QListWidget::item { padding: 8px 8px; border-radius: 8px; }
QListWidget::item:selected { background: rgba(108, 77, 255, 0.45); color: white; }
QTableWidget {
    background: rgba(255,255,255,0.05);
    alternate-background-color: rgba(255,255,255,0.03);
    color: #f3f4fb;
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 14px;
    gridline-color: rgba(255,255,255,0.06);
    selection-background-color: rgba(108, 77, 255, 0.45);
    selection-color: white;
}
QTableWidget::item { padding: 6px 8px; }
QHeaderView::section {
    background: transparent;
    color: #b7bdd0;
    padding: 10px 8px;
    border: none;
    border-bottom: 1px solid rgba(255,255,255,0.10);
    font-weight: 700;
    font-size: 12px;
}
QCheckBox { background: transparent; spacing: 8px; color: #f3f4fb; }
QScrollArea, QScrollArea#pageScroll, QWidget#page { border: none; background: transparent; }
QDialog, QMessageBox { background: #1b1e2b; }
QDialog QLabel, QMessageBox QLabel { color: #f3f4fb; }
"""

_STRETCH = {"What happened", "Student", "Package", "Heads", "Detail", "Name", "Reason"}


def current_mode() -> str:
    mode = str(QSettings("PICS", "FeeDesk").value("theme", "light") or "light")
    return mode if mode in ("light", "dark") else "light"


def set_mode(app: QApplication, mode: str) -> str:
    mode = mode if mode in ("light", "dark") else "light"
    QSettings("PICS", "FeeDesk").setValue("theme", mode)
    app.setStyleSheet(LIGHT if mode == "light" else DARK)
    return mode


def app_icon_path():
    import sys
    from pathlib import Path

    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "pics-fee.ico"
    return Path(__file__).resolve().parents[2] / "assets" / "pics-fee.ico"


def apply_app_icon(app: QApplication) -> None:
    from PySide6.QtGui import QIcon

    path = app_icon_path()
    if path.is_file():
        app.setWindowIcon(QIcon(str(path)))


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    set_mode(app, current_mode())
    apply_app_icon(app)


def rs(paisa) -> str:
    return format_rs(int(paisa or 0))


def when(value) -> str:
    return format_when(value)


def day(value) -> str:
    return format_date(value)


def button(text: str, kind: str = "") -> QPushButton:
    widget = QPushButton(text)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if kind:
        widget.setProperty("kind", kind)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
    return widget


def soften(widget: QWidget) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(28)
    effect.setOffset(0, 8)
    effect.setColor(QColor(24, 48, 78, 42))
    widget.setGraphicsEffect(effect)


def ask(parent, text: str) -> bool:
    answer = message_box(
        parent,
        QMessageBox.Icon.Question,
        text,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    ).exec()
    return answer == QMessageBox.StandardButton.Yes


def warn(parent, text: str) -> None:
    message_box(parent, QMessageBox.Icon.Warning, text).exec()


def inform(parent, text: str) -> None:
    message_box(parent, QMessageBox.Icon.Information, text).exec()


def call(parent, fn, on_unauthorized=None):
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        return fn()
    except ApiError as exc:
        if exc.status == 401 and on_unauthorized:
            on_unauthorized()
            return None
        warn(parent, exc.detail)
        return None
    except DeskError as exc:
        warn(parent, str(exc))
        return None
    finally:
        QApplication.restoreOverrideCursor()


def page_fill(page: QWidget) -> QVBoxLayout:
    layout = QVBoxLayout(page)
    layout.setContentsMargins(16, 12, 16, 16)
    layout.setSpacing(14)
    return layout


def page_fill(page: QWidget) -> QVBoxLayout:
    layout = QVBoxLayout(page)
    layout.setContentsMargins(16, 12, 16, 16)
    layout.setSpacing(14)
    return layout


def mount_page(page: QWidget) -> QVBoxLayout:
    inner = QWidget()
    inner.setObjectName("page")
    layout = QVBoxLayout(inner)
    layout.setContentsMargins(22, 18, 22, 28)
    layout.setSpacing(14)
    scroll = QScrollArea()
    scroll.setObjectName("pageScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(inner)
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.addWidget(scroll)
    return layout


def _pin_height(label: QLabel) -> QLabel:
    label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
    return label


def heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("section")
    return _pin_height(label)


def note(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("muted")
    label.setWordWrap(True)
    label.setMaximumHeight(84)
    return _pin_height(label)


def block_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("blockTitle")
    return _pin_height(label)


def toolbar(*widgets) -> QFrame:
    """One control row, with the same padding on every page."""
    frame = panel("stat")
    row = QHBoxLayout(frame)
    row.setContentsMargins(14, 12, 14, 12)
    row.setSpacing(12)
    for widget in widgets:
        if widget is None:
            row.addStretch(1)
        else:
            row.addWidget(widget, 1 if widget.__class__.__name__ == "QLineEdit" else 0)
    return frame


def panel(kind: str = "glass", expand: bool = False) -> QFrame:
    frame = QFrame()
    frame.setObjectName(kind)
    vertical = QSizePolicy.Policy.Expanding if expand else QSizePolicy.Policy.Maximum
    frame.setSizePolicy(QSizePolicy.Policy.Preferred, vertical)
    return frame


def dialog_limits() -> tuple[int, int]:
    """Largest popup that still fits a 1366×768 desk, and the screen in use."""
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        area_w, area_h = 1366, 768
    else:
        area = screen.availableGeometry()
        area_w, area_h = area.width(), area.height()
    width = min(max(area_w - 48, 480), 1200)
    height = min(max(area_h - 64, 360), 700)
    return width, height


def place_dialog(dialog: QDialog, width: int, height: int) -> None:
    max_width, max_height = dialog_limits()
    hint = dialog.sizeHint()
    if 0 < hint.height() < height:
        height = hint.height()
    width = min(max(width, 360), max_width)
    height = min(max(height, 180), max_height)
    dialog.setMaximumSize(max_width, max_height)
    dialog.setMinimumSize(min(320, max_width), min(160, max_height))
    dialog.resize(width, height)


def message_box(parent, icon, text: str, buttons=QMessageBox.StandardButton.Ok, title: str = "Fee desk") -> QMessageBox:
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(buttons)
    label = box.findChild(QLabel, "qt_msgbox_label")
    if label is not None:
        label.setWordWrap(True)
        label.setMinimumWidth(min(420, dialog_limits()[0] - 140))
        label.setMaximumWidth(min(460, dialog_limits()[0] - 120))
    decline = box.button(QMessageBox.StandardButton.No) or box.button(QMessageBox.StandardButton.Cancel)
    if decline is not None:
        decline.setProperty("kind", "quiet")
        decline.style().unpolish(decline)
        decline.style().polish(decline)
    box.adjustSize()
    place_dialog(box, max(box.sizeHint().width(), 420), max(box.sizeHint().height(), 160))
    return box


def guide(parent, title: str, text: str) -> None:
    message_box(parent, QMessageBox.Icon.Information, text, title=title).exec()


def fill_table(
    table: QTableWidget,
    headers: list[str],
    rows: list[list[str]],
    ids: list | None = None,
    fit: bool = True,
    widths: list[int] | None = None,
    visible_rows: int | None = None,
) -> None:
    table.clear()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(38)
    table.setAlternatingRowColors(True)
    table.setWordWrap(False)
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
    table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
    table.setShowGrid(False)
    for row_index, row in enumerate(rows):
        for col_index, value in enumerate(row):
            item = QTableWidgetItem("" if value is None else str(value))
            if ids is not None and col_index == 0:
                item.setData(Qt.ItemDataRole.UserRole, ids[row_index])
            table.setItem(row_index, col_index, item)
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    header.setMinimumSectionSize(88)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    if widths:
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for index, width in enumerate(widths):
            if width:
                table.setColumnWidth(index, width)
            else:
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
    else:
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        stretch = None
        if len(headers) <= 6:
            for index, name in enumerate(headers):
                if name in _STRETCH:
                    stretch = index
                    break
        if stretch is not None:
            header.setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)
    if fit:
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        cap = 12 if visible_rows is None else max(visible_rows, 1)
        visible = min(max(len(rows), 2), cap)
        header_height = header.sizeHint().height() or 40
        table.setFixedHeight(header_height + 40 * visible + 8)
    else:
        table.setMinimumHeight(180)
        table.setMaximumHeight(16777215)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


def fit_list(widget, empty_rows: int = 1) -> None:
    count = widget.count() or empty_rows
    widget.setFixedHeight(min(max(count, 1), 6) * 36 + 16)
    widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)


def selected_id(table: QTableWidget):
    row = table.currentRow()
    if row < 0:
        return None
    item = table.item(row, 0)
    if item is None:
        return None
    return item.data(Qt.ItemDataRole.UserRole)


def card(title: str, value: str = "—", tone: str = "") -> tuple[QFrame, QLabel]:
    frame = QFrame()
    frame.setObjectName("stat")
    frame.setMinimumWidth(150)
    frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(6)
    top = QHBoxLayout()
    glyph, tint, ink = {
        "good": ("Rs", "#e7f6ee", "#12a150"),
        "warn": ("!", "#fdecef", "#d4536a"),
        "info": ("i", "#e7f3ff", "#1f7a4d"),
    }.get(tone, ("•", "#e7f6ee", "#12a150"))
    icon = QLabel(glyph)
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon.setFixedSize(36, 36)
    icon.setStyleSheet(f"background: {tint}; color: {ink}; border-radius: 18px; font-weight: 700;")
    pill = QLabel()
    pill.setFixedSize(34, 18)
    pill.setStyleSheet("background: #12a150; border-radius: 9px;")
    top.addWidget(icon)
    top.addStretch(1)
    top.addWidget(pill)
    amount = QLabel(value)
    amount.setObjectName("money")
    caption = QLabel(title)
    caption.setObjectName("muted")
    caption.setWordWrap(True)
    caption.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    layout.addLayout(top)
    layout.addWidget(amount)
    layout.addWidget(caption)
    layout.addStretch(1)
    return frame, amount


class Page(QWidget):
    def __init__(self, api, on_unauthorized):
        super().__init__()
        self.api = api
        self.on_unauthorized = on_unauthorized

    def call(self, fn):
        return call(self, fn, self.on_unauthorized)

    def refresh(self) -> None:
        return None
