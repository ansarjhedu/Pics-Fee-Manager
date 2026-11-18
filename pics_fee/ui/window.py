from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pics_fee.client_api import Api
from pics_fee.constants import COLLEGE_NAME, PORT
from pics_fee.paths import data_dir
from pics_fee.security import format_fingerprint
from pics_fee.ui.dashboard import OverviewPage, search_students
from pics_fee.ui.pages_admin import ActivityPage, BackupPage, MessagesPage, StaffPage
from pics_fee.ui.pages_classes import ClassesPage, FeesPage
from pics_fee.ui.pages_desk import ApprovalPage, ClerkDesk
from pics_fee.ui.pages_records import RecordsPage
from pics_fee.ui.theme import button, call, current_mode, inform, set_mode, warn


class MainWindow(QWidget):
    def __init__(self, mode: str, host: str | None = None, port: int | None = None, fingerprint: str | None = None, lan_ips: list[str] | None = None):
        super().__init__()
        self.mode = mode
        self.host = host
        self.port = port or PORT
        self.fingerprint = fingerprint or ""
        self.lan_ips = lan_ips or []
        self.api: Api | None = None
        self.user = None
        self.setObjectName("appRoot")
        self.setWindowTitle(f"{COLLEGE_NAME} — Fee desk")
        self.setWindowIcon(QApplication.windowIcon())
        self.resize(1280, 820)
        self.setMinimumSize(1100, 700)
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.body = QVBoxLayout()
        self.root.addLayout(self.body, 1)
        if mode == "principal":
            self.api = Api(self.host, self.port, self.fingerprint)
            self._enter_from_health()
        else:
            from pics_fee.client_api import load_clerk_config

            saved = load_clerk_config()
            if saved:
                self._use_saved(saved)
            else:
                self._show_connect()

    def _clear(self) -> None:
        while self.body.count():
            item = self.body.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _mount(self, widget: QWidget) -> None:
        self._clear()
        self.body.addWidget(widget)

    def _enter_from_health(self) -> None:
        health = call(self, lambda: self.api.request("GET", "/health"))
        if health is None:
            self._show_offline()
            return
        if health.get("initialized"):
            self._show_login()
        else:
            self._show_setup()

    def _show_offline(self) -> None:
        page = _Gate("The principal's computer is not reachable.")
        retry = button("Try again")
        retry.clicked.connect(self._enter_from_health if self.mode == "principal" else self._retry_saved)
        page.layout().addWidget(retry)
        if self.mode == "clerk":
            change = button("Change connection", "quiet")
            change.clicked.connect(self._show_connect)
            page.layout().addWidget(change)
        self._mount(page)

    def _retry_saved(self) -> None:
        from pics_fee.client_api import load_clerk_config

        saved = load_clerk_config()
        if saved:
            self._use_saved(saved)
        else:
            self._show_connect()

    def _use_saved(self, saved: dict) -> None:
        try:
            self.api = Api(saved["host"], int(saved.get("port") or PORT), saved["fingerprint"])
        except Exception as exc:
            warn(self, str(exc))
            self._show_connect()
            return
        self._enter_from_health()

    def _show_connect(self) -> None:
        page = _Gate("Connect to the principal's computer")
        hint = QLabel(
            "The clerk setup file from the principal's Clerks page already fills this in. "
            "Use this screen when the principal's address has changed. Both computers must be on the college network, "
            "and the principal's desk must stay open. This computer saves only that connection. "
            "The fee records stay on the principal's computer, in C:\\ProgramData\\PICS\\FeeDesk."
        )
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        self.address = QLineEdit()
        self.address.setPlaceholderText("Address, for example 192.168.1.20")
        self.fingerprint_box = QPlainTextEdit()
        self.fingerprint_box.setPlaceholderText("Fingerprint")
        self.fingerprint_box.setFixedHeight(80)
        test = button("Test connection", "quiet")
        test.clicked.connect(self._test_connection)
        save = button("Save and continue")
        save.clicked.connect(self._save_connection)
        page.layout().addWidget(hint)
        page.layout().addWidget(QLabel("Address"))
        page.layout().addWidget(self.address)
        page.layout().addWidget(QLabel("Fingerprint"))
        page.layout().addWidget(self.fingerprint_box)
        page.layout().addWidget(test)
        page.layout().addWidget(save)
        self._mount(page)

    def _connection_api(self):
        try:
            return Api(self.address.text(), self.port, self.fingerprint_box.toPlainText())
        except Exception as exc:
            warn(self, str(exc))
            return None

    def _test_connection(self) -> None:
        api = self._connection_api()
        if api is None:
            return
        health = call(self, lambda: api.request("GET", "/health"))
        if health is not None:
            inform(self, f"Connected to {health['college']}.")

    def _save_connection(self) -> None:
        from pics_fee.client_api import save_clerk_config

        api = self._connection_api()
        if api is None:
            return
        health = call(self, lambda: api.request("GET", "/health"))
        if health is None:
            return
        try:
            save_clerk_config(self.address.text(), self.fingerprint_box.toPlainText(), self.port)
        except Exception as exc:
            warn(self, str(exc))
            return
        self.api = api
        if health.get("initialized"):
            self._show_login()
        else:
            inform(self, "Connected. The principal still needs to create an account on their computer.")
            self._show_login()

    def _identity_box(self) -> QWidget:
        box = QFrame()
        box.setObjectName("card")
        layout = QVBoxLayout(box)
        layout.addWidget(QLabel("This computer's connection"))
        records = QLabel(
            f"The fee records are stored only on this computer, in {data_dir()}. "
            "On the Clerks page, save a setup file for each clerk. That file already contains the address and fingerprint below. "
            "The clerk runs it on their computer, and their setup does not ask for either one."
        )
        records.setWordWrap(True)
        records.setObjectName("muted")
        layout.addWidget(records)
        addresses = ", ".join(self.lan_ips) if self.lan_ips else "Connect this computer to the college network to see its address."
        address = QLabel(f"Address: {addresses}\nPort: {self.port}")
        address.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(address)
        fingerprint = QPlainTextEdit(format_fingerprint(self.fingerprint))
        fingerprint.setReadOnly(True)
        fingerprint.setFixedHeight(70)
        layout.addWidget(fingerprint)
        copy = button("Copy fingerprint", "quiet")

        def copy_fingerprint():
            from PySide6.QtWidgets import QApplication

            QApplication.clipboard().setText(format_fingerprint(self.fingerprint))
            inform(self, "Fingerprint copied.")

        copy.clicked.connect(copy_fingerprint)
        layout.addWidget(copy)
        note = QLabel("If the clerk cannot connect, allow PICS Fee through Windows Firewall on this computer for port 8765.")
        note.setWordWrap(True)
        note.setObjectName("muted")
        layout.addWidget(note)
        return box

    def _show_setup(self) -> None:
        page = _Gate("Create the principal account")
        page.layout().addWidget(self._identity_box())
        self.display_name = QLineEdit()
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        for label, widget in (
            ("Your name", self.display_name),
            ("Username", self.username),
            ("Password", self.password),
            ("Confirm password", self.confirm),
        ):
            page.layout().addWidget(QLabel(label))
            page.layout().addWidget(widget)
        create = button("Create principal account")
        create.clicked.connect(self._create_admin)
        page.layout().addWidget(create)
        self._mount(page)

    def _create_admin(self) -> None:
        if self.password.text() != self.confirm.text():
            warn(self, "The two passwords do not match.")
            return
        result = call(
            self,
            lambda: self.api.request(
                "POST",
                "/setup",
                {
                    "display_name": self.display_name.text().strip(),
                    "username": self.username.text().strip(),
                    "password": self.password.text(),
                },
            ),
        )
        if result is None:
            return
        self.api.token = result["token"]
        self.user = result["user"]
        self._show_shell()

    def _show_login(self) -> None:
        page = _Gate("Sign in")
        if self.mode == "principal":
            page.layout().addWidget(self._identity_box())
        self.login_username = QLineEdit()
        if self.mode == "clerk":
            from pics_fee.client_api import load_clerk_config

            saved = load_clerk_config() or {}
            if saved.get("username"):
                self.login_username.setText(str(saved["username"]))
        self.login_password = QLineEdit()
        self.login_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_password.returnPressed.connect(self._login)
        page.layout().addWidget(QLabel("Username"))
        page.layout().addWidget(self.login_username)
        page.layout().addWidget(QLabel("Password"))
        page.layout().addWidget(self.login_password)
        sign_in = button("Sign in")
        sign_in.clicked.connect(self._login)
        page.layout().addWidget(sign_in)
        if self.mode == "principal":
            reset = button("Reset principal password on this computer", "quiet")
            reset.clicked.connect(self._reset_admin)
            page.layout().addWidget(reset)
        else:
            change = button("Change connection", "quiet")
            change.clicked.connect(self._show_connect)
            page.layout().addWidget(change)
        self._mount(page)

    def _login(self) -> None:
        result = call(
            self,
            lambda: self.api.request(
                "POST",
                "/login",
                {"username": self.login_username.text().strip(), "password": self.login_password.text()},
            ),
        )
        if result is None:
            return
        self.api.token = result["token"]
        self.user = result["user"]
        self._show_shell()

    def _reset_admin(self) -> None:
        from pics_fee.ui.dialogs import PasswordDialog

        username = self.login_username.text().strip()
        if not username:
            warn(self, "Enter the principal username first, then set a new password.")
            return
        if not warn_confirm(self):
            return
        dialog = PasswordDialog(self, "New principal password")
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        result = call(
            self,
            lambda: self.api.request(
                "POST",
                "/local/reset-admin",
                {"username": username, "password": dialog.payload, "display_name": "Principal"},
            ),
        )
        if result is not None:
            inform(self, "The principal password is updated. Sign in with it.")

    def _show_shell(self) -> None:
        shell = Shell(self.api, self.user, self._logout, self._expired, self.lan_ips, self.fingerprint, self.port)
        self._mount(shell)

    def _logout(self) -> None:
        if self.api and self.api.token:
            call(self, lambda: self.api.request("POST", "/logout"))
        if self.api:
            self.api.token = None
        self.user = None
        self._show_login()

    def _expired(self) -> None:
        if self.api:
            self.api.token = None
        self.user = None
        warn(self, "Please sign in again.")
        self._show_login()


class Shell(QWidget):
    def __init__(self, api, user, on_logout, on_unauthorized, lan_ips: list[str] | None = None, fingerprint: str = "", port: int = 8765):
        super().__init__()
        self.api = api
        self.user = user
        self.on_unauthorized = on_unauthorized
        self.lan_ips = list(lan_ips or [])
        self.fingerprint = fingerprint
        self.port = port
        self.pages = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        shell = QFrame()
        shell.setObjectName("shell")
        shell_row = QHBoxLayout(shell)
        shell_row.setContentsMargins(0, 0, 0, 0)
        shell_row.setSpacing(0)
        nav = QFrame()
        nav.setObjectName("nav")
        nav.setFixedWidth(230)
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(14, 18, 14, 16)
        nav_layout.setSpacing(4)
        brand = QHBoxLayout()
        mark = QLabel("P")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(36, 36)
        mark.setStyleSheet("background: #12a150; color: white; border-radius: 18px; font-weight: 700;")
        word = QLabel("PICS")
        word.setObjectName("headerTitle")
        word.setStyleSheet("color: #12a150;")
        brand.addWidget(mark)
        brand.addWidget(word)
        brand.addStretch(1)
        nav_layout.addLayout(brand)
        nav_layout.addSpacing(18)
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        header = QFrame()
        header.setObjectName("header")
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(18, 12, 16, 12)
        header_row.setSpacing(12)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Search students")
        self.search.setMaximumWidth(460)
        self.search.returnPressed.connect(self._search)
        self.hits = QListWidget()
        self.hits.setWindowFlags(Qt.WindowType.Popup)
        self.hits.setMinimumWidth(360)
        self.hits.itemClicked.connect(self._open_student)
        role = "Principal" if user["role"] == "admin" else "Clerk"
        avatar = QLabel((user.get("display_name") or "P")[:1].upper())
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFixedSize(36, 36)
        avatar.setStyleSheet("background: #12a150; color: white; border-radius: 18px; font-weight: 700;")
        who = QVBoxLayout()
        who.setSpacing(0)
        name = QLabel(user.get("display_name") or role)
        name.setObjectName("headerTitle")
        meta = QLabel(role)
        meta.setObjectName("headerMeta")
        who.addWidget(name)
        who.addWidget(meta)
        sign_out = button("Sign out", "quiet")
        sign_out.clicked.connect(on_logout)
        self.theme_button = button("Dark theme" if current_mode() == "light" else "Light theme", "quiet")
        self.theme_button.clicked.connect(self._toggle_theme)
        header_row.addWidget(self.search, 1)
        header_row.addStretch(1)
        header_row.addWidget(self.theme_button)
        header_row.addWidget(sign_out)
        header_row.addWidget(avatar)
        header_row.addLayout(who)
        column.addWidget(header)
        self.stack_host = QVBoxLayout()
        self.stack_host.setContentsMargins(0, 0, 0, 0)
        holder = QWidget()
        holder.setLayout(self.stack_host)
        column.addWidget(holder, 1)
        buttons = []
        if user["role"] == "admin":
            items = [
                ("Overview", OverviewPage(api, on_unauthorized, user["role"], self.show_page)),
                ("Cash waiting", ApprovalPage(api, on_unauthorized)),
                ("Classes", ClassesPage(api, on_unauthorized, user["role"])),
                ("Fees", FeesPage(api, on_unauthorized)),
                ("Clerks", StaffPage(api, on_unauthorized, self.lan_ips, self.fingerprint, self.port)),
                ("Records", RecordsPage(api, on_unauthorized)),
                ("Messages", MessagesPage(api, on_unauthorized)),
                ("Backup", BackupPage(api, on_unauthorized)),
                ("Activity", ActivityPage(api, on_unauthorized)),
            ]
        else:
            items = [
                ("Overview", OverviewPage(api, on_unauthorized, user["role"], self.show_page)),
                ("Desk", ClerkDesk(api, on_unauthorized)),
                ("Classes", ClassesPage(api, on_unauthorized, user["role"])),
                ("Records", RecordsPage(api, on_unauthorized)),
            ]
        icons = {
            "Overview": "▣",
            "Cash waiting": "₨",
            "Desk": "₨",
            "Classes": "☰",
            "Fees": "₹",
            "Clerks": "☺",
            "Records": "▤",
            "Messages": "✉",
            "Backup": "⇩",
            "Activity": "↻",
        }
        for label, page in items:
            nav_button = button(f"{icons.get(label, '•')}    {label}", "nav")
            nav_button.setCheckable(True)
            nav_button.setMinimumHeight(40)
            nav_layout.addWidget(nav_button)
            buttons.append(nav_button)
            self.pages[label] = page
            nav_button.clicked.connect(lambda _checked=False, name=label: self.show_page(name))
        nav_layout.addStretch(1)
        shell_row.addWidget(nav)
        shell_row.addLayout(column, 1)
        outer.addWidget(shell)
        self.nav_buttons = dict(zip((label for label, _page in items), buttons))
        self.show_page(items[0][0])

    def _search(self) -> None:
        text = self.search.text().strip()
        if not text:
            return
        rows = call(self, lambda: search_students(self.api, text))
        if not rows:
            return
        self.hits.clear()
        for row in rows[:12]:
            item = QListWidgetItem(f"{row['name']}   ·   {row['admission_no']}   ·   {row['class_name']}")
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.hits.addItem(item)
        self.hits.setFixedHeight(min(self.hits.count(), 8) * 40 + 8)
        self.hits.move(self.search.mapToGlobal(self.search.rect().bottomLeft()))
        self.hits.show()

    def _open_student(self, item: QListWidgetItem) -> None:
        from pics_fee.ui.pages_students import LedgerDialog

        self.hits.hide()
        student_id = item.data(Qt.ItemDataRole.UserRole)
        if student_id is None:
            return
        LedgerDialog(self, self.api, self.on_unauthorized, self.user["role"], int(student_id)).exec()

    def show_page(self, name: str) -> None:
        while self.stack_host.count():
            item = self.stack_host.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        page = self.pages[name]
        self.stack_host.addWidget(page)
        for label, nav_button in self.nav_buttons.items():
            nav_button.setChecked(label == name)
        page.refresh()

    def _toggle_theme(self) -> None:
        from PySide6.QtWidgets import QApplication

        mode = "dark" if current_mode() == "light" else "light"
        set_mode(QApplication.instance(), mode)
        self.theme_button.setText("Dark theme" if mode == "light" else "Light theme")


class _Gate(QWidget):
    def __init__(self, title: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 36, 48, 36)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName("section")
        layout.addWidget(heading)

    def layout(self):
        return super().layout()


def warn_confirm(parent) -> bool:
    from pics_fee.ui.theme import ask

    return ask(parent, "Reset the principal password on this computer? Anyone using this computer can do this.")
