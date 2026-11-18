from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
)

from pics_fee.constants import TEMPLATE_FIELDS
from pics_fee.ui.dialogs import ClerkDialog, NameDialog, PackageDialog, PasswordDialog
from pics_fee.ui.theme import (
    Page,
    ask,
    block_title,
    button,
    day,
    fill_table,
    fit_list,
    heading,
    inform,
    page_fill,
    toolbar,
    panel,
    mount_page,
    note,
    rs,
    selected_id,
    warn,
    when,
)


class FeesPage(Page):
    def __init__(self, api, on_unauthorized):
        super().__init__(api, on_unauthorized)
        root = mount_page(self)
        root.addWidget(heading("Fee setup"))
        root.addWidget(note("Build a package for each class and session. Students keep a copy, so later edits do not rewrite them."))
        row = QHBoxLayout()
        row.setSpacing(14)
        left = panel()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(8)
        left_layout.addWidget(block_title("Classes"))
        self.classes = QListWidget()
        left_layout.addWidget(self.classes)
        class_row = QHBoxLayout()
        add_class = button("Add class", "quiet")
        add_class.clicked.connect(self._add_class)
        remove_class = button("Remove", "danger")
        remove_class.clicked.connect(self._remove_class)
        class_row.addWidget(add_class)
        class_row.addWidget(remove_class)
        class_row.addStretch(1)
        left_layout.addLayout(class_row)
        left_layout.addWidget(block_title("Sessions"))
        self.sessions = QListWidget()
        left_layout.addWidget(self.sessions)
        session_row = QHBoxLayout()
        add_session = button("Add session", "quiet")
        add_session.clicked.connect(self._add_session)
        remove_session = button("Remove", "danger")
        remove_session.clicked.connect(self._remove_session)
        session_row.addWidget(add_session)
        session_row.addWidget(remove_session)
        session_row.addStretch(1)
        left_layout.addLayout(session_row)
        right = panel()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(8)
        right_layout.addWidget(block_title("Fee packages"))
        self.packages = QTableWidget()
        right_layout.addWidget(self.packages)
        package_row = QHBoxLayout()
        add_package = button("New package")
        add_package.clicked.connect(self._add_package)
        edit_package = button("Edit", "quiet")
        edit_package.clicked.connect(self._edit_package)
        remove_package = button("Remove", "danger")
        remove_package.clicked.connect(self._remove_package)
        package_row.addWidget(add_package)
        package_row.addWidget(edit_package)
        package_row.addWidget(remove_package)
        package_row.addStretch(1)
        right_layout.addLayout(package_row)
        row.addWidget(left, 1)
        row.addWidget(right, 2)
        root.addLayout(row)
        self._classes = []
        self._sessions = []
        self._packages = []

    def refresh(self) -> None:
        classes = self.call(lambda: self.api.request("GET", "/classes"))
        sessions = self.call(lambda: self.api.request("GET", "/sessions"))
        packages = self.call(lambda: self.api.request("GET", "/packages"))
        if classes is None or sessions is None or packages is None:
            return
        self._classes, self._sessions, self._packages = classes, sessions, packages
        self.classes.clear()
        for row in classes:
            self.classes.addItem(row["name"])
            self.classes.item(self.classes.count() - 1).setData(256, row["id"])
        self.sessions.clear()
        for row in sessions:
            self.sessions.addItem(row["name"])
            self.sessions.item(self.sessions.count() - 1).setData(256, row["id"])
        fit_list(self.classes)
        fit_list(self.sessions)
        fill_table(
            self.packages,
            ["Package", "Class", "Session", "Heads"],
            [
                [
                    row["name"],
                    row["class_name"],
                    row["session_name"],
                    ", ".join(item["head_name"] for item in row["items"]),
                ]
                for row in packages
            ],
            [row["id"] for row in packages],
        )

    def _list_id(self, widget: QListWidget):
        item = widget.currentItem()
        if item is None:
            return None
        return item.data(256)

    def _add_class(self) -> None:
        dialog = NameDialog(self, "Add class", "Class name")
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        if self.call(lambda: self.api.request("POST", "/classes", {"name": dialog.payload})) is not None:
            self.refresh()

    def _remove_class(self) -> None:
        class_id = self._list_id(self.classes)
        if class_id is None:
            warn(self, "Select a class first.")
            return
        if not ask(self, "Remove this class?"):
            return
        if self.call(lambda: self.api.request("DELETE", f"/classes/{class_id}")) is not None:
            self.refresh()

    def _add_session(self) -> None:
        dialog = NameDialog(self, "Add session", "Session, for example 2026-27")
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        if self.call(lambda: self.api.request("POST", "/sessions", {"name": dialog.payload})) is not None:
            self.refresh()

    def _remove_session(self) -> None:
        session_id = self._list_id(self.sessions)
        if session_id is None:
            warn(self, "Select a session first.")
            return
        if not ask(self, "Remove this session?"):
            return
        if self.call(lambda: self.api.request("DELETE", f"/sessions/{session_id}")) is not None:
            self.refresh()

    def _add_package(self) -> None:
        dialog = PackageDialog(self, self._classes, self._sessions)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        if self.call(lambda: self.api.request("POST", "/packages", dialog.payload)) is not None:
            self.refresh()

    def _edit_package(self) -> None:
        package_id = selected_id(self.packages)
        package = next((row for row in self._packages if row["id"] == package_id), None)
        if package is None:
            warn(self, "Select a fee package first.")
            return
        dialog = PackageDialog(self, self._classes, self._sessions, package)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        if self.call(lambda: self.api.request("PUT", f"/packages/{package_id}", dialog.payload)) is not None:
            self.refresh()

    def _remove_package(self) -> None:
        package_id = selected_id(self.packages)
        if package_id is None:
            warn(self, "Select a fee package first.")
            return
        if not ask(self, "Remove this fee package?"):
            return
        if self.call(lambda: self.api.request("DELETE", f"/packages/{package_id}")) is not None:
            self.refresh()


class StaffPage(Page):
    def __init__(self, api, on_unauthorized, lan_ips: list[str] | None = None, fingerprint: str = "", port: int = 8765):
        super().__init__(api, on_unauthorized)
        self._activity = []
        self._lan_ips = list(lan_ips or [])
        self._fingerprint = fingerprint
        self._port = port
        root = page_fill(self)
        root.addWidget(heading("Clerks"))
        root.addWidget(note("Add a clerk, then save their setup file. That file already contains this computer's address and fingerprint."))
        body = QHBoxLayout()
        body.setSpacing(12)
        left = QVBoxLayout()
        self.table = QTableWidget()
        self.table.itemSelectionChanged.connect(self._show_activity)
        left.addWidget(self.table, 1)
        add = button("New clerk")
        add.clicked.connect(self._add)
        reset = button("Reset password", "quiet")
        reset.clicked.connect(self._reset)
        toggle = button("Turn on / off", "quiet")
        toggle.clicked.connect(self._toggle)
        left.addWidget(toolbar(add, reset, toggle, None))
        body.addLayout(left, 2)
        side = panel(expand=True)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(16, 16, 16, 16)
        side_layout.setSpacing(8)
        self.clerk_title = block_title("Select a clerk")
        self.clerk_note = note("Recent sign-ins, students, and cash recorded by this clerk.")
        side_layout.addWidget(self.clerk_title)
        side_layout.addWidget(self.clerk_note)
        side_layout.addWidget(note("Save a setup file and copy it to this clerk's computer. Running it installs their desk with the connection already filled in."))
        self.address_pick = QComboBox()
        self.address_pick.setMinimumHeight(40)
        side_layout.addWidget(self.address_pick)
        save_setup = button("Save setup file")
        save_setup.clicked.connect(self._save_setup)
        side_layout.addWidget(save_setup)
        self.activity = QTableWidget()
        side_layout.addWidget(self.activity, 1)
        body.addWidget(side, 3)
        root.addLayout(body, 1)
        self._rows = []
        self._fill_addresses()

    def refresh(self) -> None:
        rows = self.call(lambda: self.api.request("GET", "/staff/clerks"))
        if rows is None:
            return
        self._rows = rows
        activity = self.call(lambda: self.api.request("GET", "/audit?limit=400"))
        self._activity = activity or []
        fill_table(
            self.table,
            ["Name", "Username", "Status"],
            [[row["display_name"], row["username"], "On" if row["active"] else "Off"] for row in rows],
            [row["id"] for row in rows],
            fit=False,
            widths=[0, 140, 80],
        )
        if self.table.rowCount() and self.table.currentRow() < 0:
            self.table.selectRow(0)
        self._show_activity()

    def _show_activity(self) -> None:
        row = self.table.currentRow()
        if row < 0 or not self._rows:
            self.clerk_title.setText("Select a clerk")
            fill_table(self.activity, ["When", "What happened"], [], fit=False)
            return
        user_id = selected_id(self.table)
        clerk = next((item for item in self._rows if item["id"] == user_id), None)
        if clerk is None:
            return
        self.clerk_title.setText(clerk["display_name"])
        self.clerk_note.setText("On" if clerk["active"] else "Off")
        lines = [item for item in self._activity if item["username"] == clerk["username"]]
        fill_table(
            self.activity,
            ["When", "What happened"],
            [[when(item["created_at"]), item["summary"]] for item in lines],
            [item["id"] for item in lines],
            fit=False,
            widths=[170, 0],
        )

    def _selected(self):
        user_id = selected_id(self.table)
        if user_id is None:
            warn(self, "Select a clerk first.")
            return None
        return next((row for row in self._rows if row["id"] == user_id), None)

    def _select_id(self, user_id) -> None:
        if user_id is None:
            return
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == user_id:
                self.table.selectRow(row)
                return

    def _fill_addresses(self) -> None:
        from pics_fee.certs import lan_ips

        current = self.address_pick.currentText()
        found = lan_ips() or list(self._lan_ips)
        self.address_pick.clear()
        self.address_pick.addItems(found)
        if current:
            index = self.address_pick.findText(current)
            if index >= 0:
                self.address_pick.setCurrentIndex(index)

    def _save_setup(self) -> None:
        from pics_fee.clerk_setup import write_clerk_setup

        row = self._selected()
        if row is None:
            return
        self._fill_addresses()
        host = self.address_pick.currentText().strip()
        if not host:
            warn(self, "Connect this computer to the college network, then save the clerk setup again.")
            return
        safe = "".join(ch for ch in row["display_name"] if ch not in '<>:"/\\|?*').strip() or row["username"]
        desktop = str(Path.home() / "Desktop" / f"PICS Fee Desk - {safe}.exe")
        dest, _chosen = QFileDialog.getSaveFileName(self, "Save clerk setup", desktop, "Setup (*.exe)")
        if not dest:
            return
        if not dest.lower().endswith(".exe"):
            dest += ".exe"
        try:
            config = write_clerk_setup(Path(dest), host, self._port, self._fingerprint, row["username"])
        except Exception as exc:
            warn(self, str(exc))
            return
        inform(
            self,
            f"Saved the setup for {row['display_name']}. Copy this file to their computer and run it. "
            f"It already connects to {config['host']}.",
        )

    def _add(self) -> None:
        dialog = ClerkDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        created = self.call(lambda: self.api.request("POST", "/staff/clerks", dialog.payload))
        if created is not None:
            self.refresh()
            self._select_id(created.get("id"))
            self._save_setup()

    def _reset(self) -> None:
        row = self._selected()
        if row is None:
            return
        dialog = PasswordDialog(self, f"New password for {row['display_name']}")
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        result = self.call(
            lambda: self.api.request("POST", f"/staff/clerks/{row['id']}/password", {"password": dialog.payload})
        )
        if result is not None:
            inform(self, "The clerk will need the new password at the next sign-in.")

    def _toggle(self) -> None:
        row = self._selected()
        if row is None:
            return
        result = self.call(
            lambda: self.api.request("POST", f"/staff/clerks/{row['id']}/active", {"active": not row["active"]})
        )
        if result is not None:
            self.refresh()


class MessagesPage(Page):
    def __init__(self, api, on_unauthorized):
        super().__init__(api, on_unauthorized)
        root = mount_page(self)
        root.addWidget(heading("Messages"))
        root.addWidget(
            note(
                "Paid successfully is sent when you approve the cash. Fee is due is sent from the reminder list. "
                f"You can use {', '.join('{' + name + '}' for name in TEMPLATE_FIELDS)}."
            )
        )
        settings = panel()
        settings_layout = QVBoxLayout(settings)
        settings_layout.setContentsMargins(16, 16, 16, 16)
        form = QFormLayout()
        form.setSpacing(10)
        self.test_mode = QCheckBox("Test mode (do not send real SMS)")
        self.api_url = QLineEdit()
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.sender = QLineEdit()
        self.payment_template = QPlainTextEdit()
        self.payment_template.setFixedHeight(88)
        self.reminder_template = QPlainTextEdit()
        self.reminder_template.setFixedHeight(88)
        form.addRow("Paid successfully", self.payment_template)
        form.addRow("Fee is due", self.reminder_template)
        form.addRow(self.test_mode)
        form.addRow("SMS address", self.api_url)
        form.addRow("SMS key", self.api_key)
        form.addRow("Sender mask", self.sender)
        settings_layout.addLayout(form)
        self.key_label = QLabel("")
        self.key_label.setObjectName("muted")
        self.key_label.setWordWrap(True)
        settings_layout.addWidget(self.key_label)
        save = button("Save message settings")
        save.clicked.connect(self._save)
        settings_layout.addWidget(save, alignment=Qt.AlignmentFlag.AlignLeft)
        root.addWidget(settings)
        reminder_row = QHBoxLayout()
        self.within = QSpinBox()
        self.within.setRange(0, 365)
        self.within.setValue(7)
        self.include_all = QCheckBox("Everyone who still owes")
        show = button("Show reminders", "quiet")
        show.clicked.connect(self._load_reminders)
        send = button("Send shown reminders")
        send.clicked.connect(self._send)
        reminder_row.addWidget(QLabel("Last date within days"))
        reminder_row.addWidget(self.within)
        reminder_row.addWidget(self.include_all)
        reminder_row.addWidget(show)
        reminder_row.addWidget(send)
        reminder_row.addStretch(1)
        root.addWidget(block_title("Reminders"))
        root.addLayout(reminder_row)
        self.reminders = QTableWidget()
        self.reminders.setFixedHeight(150)
        root.addWidget(self.reminders)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFixedHeight(88)
        root.addWidget(self.preview)
        self.reminders.itemSelectionChanged.connect(self._preview)
        root.addWidget(block_title("Message log"))
        self.log = QTableWidget()
        self.log.setFixedHeight(180)
        root.addWidget(self.log)
        retry = button("Send failed message again", "quiet")
        retry.clicked.connect(self._retry)
        root.addWidget(retry, alignment=Qt.AlignmentFlag.AlignLeft)
        self._reminder_rows = []

    def refresh(self) -> None:
        settings = self.call(lambda: self.api.request("GET", "/sms/settings"))
        log = self.call(lambda: self.api.request("GET", "/sms/log"))
        if settings is None or log is None:
            return
        self.test_mode.setChecked(settings["test_mode"])
        self.api_url.setText(settings["api_url"])
        self.sender.setText(settings["sender"])
        self.payment_template.setPlainText(settings["payment_template"])
        self.reminder_template.setPlainText(settings["reminder_template"])
        self.api_key.clear()
        self.api_key.setPlaceholderText("Leave blank to keep the saved key" if settings["key_set"] else "SMS key")
        self.key_label.setText(f"Saved key: {settings['key_masked']}" if settings["key_set"] else "No SMS key saved yet.")
        fill_table(
            self.log,
            ["When", "Student", "Kind", "Status", "Detail"],
            [
                [
                    when(row["sent_at"] or row["created_at"]),
                    row["student_name"],
                    row["kind"],
                    "Logged, not sent" if row["provider_ref"] == "TEST-NOT-SENT" else row["status"],
                    row["error"] or row["provider_ref"],
                ]
                for row in log
            ],
            [row["id"] for row in log],
        )
        self._log = log

    def _save(self) -> None:
        payload = {
            "test_mode": self.test_mode.isChecked(),
            "api_url": self.api_url.text().strip(),
            "api_key": self.api_key.text().strip(),
            "sender": self.sender.text().strip(),
            "payment_template": self.payment_template.toPlainText(),
            "reminder_template": self.reminder_template.toPlainText(),
        }
        if self.call(lambda: self.api.request("PUT", "/sms/settings", payload)) is not None:
            inform(self, "Message settings saved.")
            self.refresh()

    def _load_reminders(self) -> None:
        include = "true" if self.include_all.isChecked() else "false"
        rows = self.call(
            lambda: self.api.request("GET", f"/sms/reminders?within_days={self.within.value()}&include_all={include}")
        )
        if rows is None:
            return
        self._reminder_rows = rows
        fill_table(
            self.reminders,
            ["Student", "Class", "Mobile", "Remaining", "Last date"],
            [
                [row["student_name"], row["class_name"], row["phone"], rs(row["remaining_paisa"]), day(row["next_due"])]
                for row in rows
            ],
            [row["student_id"] for row in rows],
        )

    def _preview(self) -> None:
        student_id = selected_id(self.reminders)
        row = next((item for item in self._reminder_rows if item["student_id"] == student_id), None)
        self.preview.setPlainText("" if row is None else row.get("body") or row.get("error") or "")

    def _send(self) -> None:
        if not self._reminder_rows:
            warn(self, "Show the reminder list first.")
            return
        if not ask(self, f"Send {len(self._reminder_rows)} reminder(s)?"):
            return
        ids = [row["student_id"] for row in self._reminder_rows if row.get("body")]
        result = self.call(lambda: self.api.request("POST", "/sms/reminders", {"student_ids": ids}))
        if result is not None:
            inform(self, f"Queued {result['queued']} reminder(s).")
            self.refresh()

    def _retry(self) -> None:
        message_id = selected_id(self.log)
        if message_id is None:
            warn(self, "Select a message first.")
            return
        if self.call(lambda: self.api.request("POST", f"/sms/{message_id}/retry")) is not None:
            self.refresh()


class BackupPage(Page):
    def __init__(self, api, on_unauthorized):
        super().__init__(api, on_unauthorized)
        root = page_fill(self)
        root.addWidget(heading("Backup"))
        box = panel()
        panel_layout = QVBoxLayout(box)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(12)
        self.detail = QLabel("The records stay on the principal's computer.")
        self.detail.setWordWrap(True)
        self.detail.setObjectName("muted")
        panel_layout.addWidget(self.detail)
        local = button("Save a backup in the fee folder")
        local.clicked.connect(self._local)
        copy = button("Save a backup copy…", "quiet")
        copy.clicked.connect(self._download)
        actions = QHBoxLayout()
        actions.addWidget(local)
        actions.addWidget(copy)
        actions.addStretch(1)
        panel_layout.addLayout(actions)
        root.addWidget(box)

    def refresh(self) -> None:
        info = self.call(lambda: self.api.request("GET", "/admin/info"))
        if info is None:
            return
        last = info["last_backup"] or "none yet"
        self.detail.setText(
            f"Records folder on the principal's computer:\n{info['data_dir']}\n\n"
            f"Backups:\n{info['backup_dir']}\n\n"
            f"Latest backup: {last}\n\n"
            "A backup is also saved each time the principal's computer opens the fee desk. "
            "The SMS key can be read again only on this Windows account."
        )

    def _local(self) -> None:
        result = self.call(lambda: self.api.request("POST", "/admin/backup"))
        if result is not None:
            inform(self, f"Backup saved on the principal's computer:\n{result['path']}")
            self.refresh()

    def _download(self) -> None:
        data = self.call(lambda: self.api.request_bytes("GET", "/admin/backup/download"))
        if data is None:
            return
        path, _selected = QFileDialog.getSaveFileName(self, "Save backup", "pics-fee-backup.db", "Database (*.db)")
        if not path:
            return
        Path(path).write_bytes(data)
        inform(self, "Backup copy saved.")
        self.refresh()


class ActivityPage(Page):
    def __init__(self, api, on_unauthorized):
        super().__init__(api, on_unauthorized)
        root = page_fill(self)
        root.addWidget(heading("Activity"))
        self.who = QComboBox()
        self.who.setMinimumWidth(180)
        self.who.addItem("Everyone", "")
        self.who.currentIndexChanged.connect(self._filter)
        root.addWidget(toolbar(self.who, None))
        root.addWidget(note("Sign-ins, student changes, cash, approvals, and messages."))
        self.table = QTableWidget()
        root.addWidget(self.table, 1)
        self._rows = []

    def refresh(self) -> None:
        rows = self.call(lambda: self.api.request("GET", "/audit?limit=500"))
        if rows is None:
            return
        self._rows = rows
        chosen = self.who.currentData()
        names = sorted({row["username"] for row in rows if row["username"]})
        self.who.blockSignals(True)
        self.who.clear()
        self.who.addItem("Everyone", "")
        for name in names:
            self.who.addItem(name, name)
        index = self.who.findData(chosen)
        self.who.setCurrentIndex(index if index >= 0 else 0)
        self.who.blockSignals(False)
        self._filter()

    def _filter(self) -> None:
        username = self.who.currentData() or ""
        rows = [row for row in self._rows if not username or row["username"] == username]
        fill_table(
            self.table,
            ["When", "Who", "What happened", "Computer"],
            [[when(row["created_at"]), row["username"], row["summary"], row["machine"]] for row in rows],
            [row["id"] for row in rows],
            fit=False,
            widths=[180, 140, 0, 160],
        )
