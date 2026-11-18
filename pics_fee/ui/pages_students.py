from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from pics_fee.ui.dialogs import AdjustmentDialog, ConcessionDialog, PaymentDialog, StudentDialog
from pics_fee.ui.theme import (
    Page,
    ask,
    button,
    card,
    fill_table,
    heading,
    inform,
    mount_page,
    note,
    place_dialog,
    rs,
    selected_id,
    warn,
    day,
)


class StudentsPage(Page):
    def __init__(self, api, on_unauthorized, role: str):
        super().__init__(api, on_unauthorized)
        self.role = role
        root = mount_page(self)
        root.addWidget(heading("Students"))
        root.addWidget(note("Search by name, father, admission number, or mobile. Open a row to see that student's fee record."))
        filters = QHBoxLayout()
        filters.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Name, father, admission number, or mobile")
        self.search.returnPressed.connect(self.refresh)
        self.class_filter = QComboBox()
        self.session_filter = QComboBox()
        self.status_filter = QComboBox()
        self.status_filter.addItem("Active", "active")
        self.status_filter.addItem("Left", "left")
        self.status_filter.addItem("All", "all")
        filters.addWidget(self.search, 2)
        filters.addWidget(self.class_filter, 1)
        filters.addWidget(self.session_filter, 1)
        filters.addWidget(self.status_filter)
        find = button("Show", "quiet")
        find.clicked.connect(self.refresh)
        filters.addWidget(find)
        root.addLayout(filters)
        self.summary = note("")
        root.addWidget(self.summary)
        self.table = QTableWidget()
        self.table.doubleClicked.connect(self._open)
        root.addWidget(self.table)
        actions = QHBoxLayout()
        add = button("Add student")
        add.clicked.connect(self._add)
        edit = button("Edit", "quiet")
        edit.clicked.connect(self._edit)
        open_btn = button("Open record", "quiet")
        open_btn.clicked.connect(self._open)
        actions.addWidget(add)
        actions.addWidget(edit)
        actions.addWidget(open_btn)
        if role == "clerk":
            take = button("Take payment")
            take.clicked.connect(self._take)
            actions.addWidget(take)
        remove = button("Remove", "danger")
        remove.clicked.connect(self._remove)
        actions.addWidget(remove)
        actions.addStretch(1)
        root.addLayout(actions)
        self._rows: list[dict] = []
        self.class_filter.currentIndexChanged.connect(self.refresh)
        self.session_filter.currentIndexChanged.connect(self.refresh)
        self.status_filter.currentIndexChanged.connect(self.refresh)

    def refresh(self) -> None:
        classes = self.call(lambda: self.api.request("GET", "/classes"))
        sessions = self.call(lambda: self.api.request("GET", "/sessions"))
        if classes is None or sessions is None:
            return
        self._fill_filter(self.class_filter, "All classes", classes)
        self._fill_filter(self.session_filter, "All sessions", sessions)
        params = [f"status={self.status_filter.currentData()}", f"search={_quote(self.search.text().strip())}"]
        if self.class_filter.currentData():
            params.append(f"class_id={self.class_filter.currentData()}")
        if self.session_filter.currentData():
            params.append(f"session_id={self.session_filter.currentData()}")
        rows = self.call(lambda: self.api.request("GET", "/students?" + "&".join(params)))
        if rows is None:
            return
        self._rows = rows
        waiting = sum(row["waiting_paisa"] for row in rows)
        remaining = sum(row["remaining_paisa"] for row in rows)
        self.summary.setText(f"{len(rows)} student(s) shown. Waiting {rs(waiting)}. Still to collect {rs(remaining)}.")
        fill_table(
            self.table,
            ["Admission", "Student", "Father", "Class", "Section", "Mobile", "Total", "Paid", "Waiting", "Remaining"],
            [
                [
                    row["admission_no"],
                    row["name"],
                    row["father_name"],
                    row["class_name"],
                    row["section"],
                    row["phone"],
                    rs(row["total_paisa"]),
                    rs(row["paid_paisa"]),
                    rs(row["waiting_paisa"]),
                    rs(row["remaining_paisa"]),
                ]
                for row in rows
            ],
            [row["id"] for row in rows],
        )

    def _fill_filter(self, box: QComboBox, first: str, rows: list[dict]) -> None:
        current = box.currentData()
        box.blockSignals(True)
        box.clear()
        box.addItem(first, None)
        for row in rows:
            box.addItem(row["name"], row["id"])
        index = box.findData(current)
        box.setCurrentIndex(index if index >= 0 else 0)
        box.blockSignals(False)

    def _selected(self):
        student_id = selected_id(self.table)
        if student_id is None:
            warn(self, "Select a student first.")
            return None
        return next((row for row in self._rows if row["id"] == student_id), None)

    def _catalog(self):
        classes = self.call(lambda: self.api.request("GET", "/classes"))
        sessions = self.call(lambda: self.api.request("GET", "/sessions"))
        packages = self.call(lambda: self.api.request("GET", "/packages"))
        if classes is None or sessions is None or packages is None:
            return None
        return classes, sessions, packages

    def _add(self) -> None:
        catalog = self._catalog()
        if catalog is None:
            return
        dialog = StudentDialog(self, *catalog)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        result = self.call(lambda: self.api.request("POST", "/students", dialog.payload))
        if result is not None:
            self.refresh()

    def _edit(self) -> None:
        row = self._selected()
        catalog = self._catalog()
        if row is None or catalog is None:
            return
        dialog = StudentDialog(self, *catalog, student=row)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        result = self.call(lambda: self.api.request("PUT", f"/students/{row['id']}", dialog.payload))
        if result is not None:
            self.refresh()

    def _open(self) -> None:
        row = self._selected()
        if row is None:
            return
        dialog = LedgerDialog(self, self.api, self.on_unauthorized, self.role, row["id"])
        dialog.exec()
        self.refresh()

    def _take(self) -> None:
        row = self._selected()
        if row is None:
            return
        ledger = self.call(lambda: self.api.request("GET", f"/students/{row['id']}"))
        if ledger is None:
            return
        dialog = PaymentDialog(self, ledger)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        from pics_fee.printing import print_voucher

        voucher = self.call(
            lambda: self.api.request(
                "POST",
                "/payments",
                {"student_id": row["id"], "amount_rupees": dialog.payload},
            )
        )
        if voucher is None:
            return
        inform(self, f"Voucher {voucher['voucher_no']} is in the drawer.")
        print_voucher(self, voucher)
        self.refresh()

    def _remove(self) -> None:
        row = self._selected()
        if row is None:
            return
        if not row.get("can_delete"):
            warn(self, "This student has fee history, so the record stays. Open the record and mark the student as left.")
            return
        if not ask(self, f"Remove {row['name']}? This cannot be undone."):
            return
        result = self.call(lambda: self.api.request("DELETE", f"/students/{row['id']}"))
        if result is not None:
            self.refresh()


class _PackageDialog(QDialog):
    def __init__(self, parent, packages: list[dict]):
        super().__init__(parent)
        self.setWindowTitle("Fee package")
        self.package = None
        self.packages = packages
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)
        title = QLabel("Add this package to the student")
        title.setObjectName("section")
        title.setWordWrap(True)
        root.addWidget(title)
        hint = QLabel("The package is copied onto this student. Later edits to the package do not change the record.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        root.addWidget(hint)
        self.box = QComboBox()
        for package in packages:
            self.box.addItem(package["name"], package["id"])
        root.addWidget(self.box)
        actions = QHBoxLayout()
        actions.setSpacing(10)
        ok = button("Add package")
        cancel = button("Cancel", "quiet")
        ok.clicked.connect(self._accept)
        cancel.clicked.connect(self.reject)
        actions.addWidget(ok)
        actions.addWidget(cancel)
        actions.addStretch(1)
        root.addLayout(actions)
        place_dialog(self, 480, 280)

    def _accept(self) -> None:
        package_id = self.box.currentData()
        self.package = next((item for item in self.packages if item["id"] == package_id), None)
        if self.package is not None:
            self.accept()


class LedgerDialog(QDialog):
    def __init__(self, parent, api, on_unauthorized, role: str, student_id: int):
        super().__init__(parent)
        self.api = api
        self.on_unauthorized = on_unauthorized
        self.role = role
        self.student_id = student_id
        self.data = None
        self.setWindowTitle("Student record")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)
        self.heading = QLabel("")
        self.heading.setObjectName("section")
        self.heading.setWordWrap(True)
        root.addWidget(self.heading)
        identity = QFrame()
        identity.setObjectName("card")
        grid = QGridLayout(identity)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        self.identity = {}
        for row, column, caption, key in (
            (0, 0, "Father", "father"),
            (0, 1, "Mobile", "phone"),
            (1, 0, "Class", "class"),
            (1, 1, "Session", "session"),
            (2, 0, "Status", "status"),
            (2, 1, "Next last date", "due"),
        ):
            block = QVBoxLayout()
            block.setSpacing(2)
            cap = QLabel(caption)
            cap.setObjectName("muted")
            value = QLabel("—")
            value.setWordWrap(True)
            block.addWidget(cap)
            block.addWidget(value)
            grid.addLayout(block, row, column)
            self.identity[key] = value
        root.addWidget(identity)
        stats = QHBoxLayout()
        stats.setSpacing(10)
        total, self.total_value = card("Total", "Rs 0", "info")
        paid, self.paid_value = card("Paid", "Rs 0", "good")
        waiting, self.waiting_value = card("Waiting", "Rs 0", "warn")
        remaining, self.remaining_value = card("Remaining", "Rs 0")
        for widget in (total, paid, waiting, remaining):
            widget.setMinimumWidth(120)
            stats.addWidget(widget)
        root.addLayout(stats)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumHeight(160)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)
        self.charges = self._section(body_layout, "Fee heads")
        self.payments = self._section(body_layout, "Vouchers")
        self.adjustments = self._section(body_layout, "Corrections")
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        actions = QHBoxLayout()
        actions.setSpacing(10)
        if role == "clerk":
            take = button("Take payment")
            take.clicked.connect(self._take)
            actions.addWidget(take)
        package = button("Add fee package", "quiet")
        package.clicked.connect(self._package)
        actions.addWidget(package)
        if role == "admin":
            concession = button("Concession", "quiet")
            concession.clicked.connect(self._concession)
            correct = button("Correction", "quiet")
            correct.clicked.connect(self._adjust)
            actions.addWidget(concession)
            actions.addWidget(correct)
        self.status_button = button("Mark left", "quiet")
        self.status_button.clicked.connect(self._status)
        actions.addWidget(self.status_button)
        close = button("Close", "quiet")
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        actions.addStretch(1)
        root.addLayout(actions)
        self.reload()
        place_dialog(self, 1000, 680)

    def _section(self, layout, title: str) -> QTableWidget:
        label = QLabel(title)
        label.setObjectName("blockTitle")
        layout.addWidget(label)
        table = QTableWidget()
        layout.addWidget(table)
        return table

    def call(self, fn):
        from pics_fee.ui.theme import call

        return call(self, fn, self.on_unauthorized)

    def reload(self) -> None:
        data = self.call(lambda: self.api.request("GET", f"/students/{self.student_id}"))
        if data is None:
            return
        self.data = data
        self.heading.setText(f"{data['name']}  ·  {data['admission_no']}")
        due = day(data["next_due"]) if data["remaining_paisa"] > 0 else "Paid in full"
        section = data.get("section") or ""
        class_name = data["class_name"] + (f" · {section}" if section else "")
        self.identity["father"].setText(data["father_name"] or "—")
        self.identity["phone"].setText(data["phone"] or "—")
        self.identity["class"].setText(class_name)
        self.identity["session"].setText(data["session_name"] or "—")
        self.identity["status"].setText(data["status"].title())
        self.identity["due"].setText(due)
        self.total_value.setText(rs(data["total_paisa"]))
        self.paid_value.setText(rs(data["paid_paisa"]))
        self.waiting_value.setText(rs(data["waiting_paisa"]))
        self.remaining_value.setText(rs(data["remaining_paisa"]))
        self.status_button.setText("Mark active" if data["status"] == "left" else "Mark left")
        fill_table(
            self.charges,
            ["Head", "Amount", "Concession", "Due", "Paid", "Remaining"],
            [
                [
                    row["head_name"],
                    rs(row["amount_paisa"]),
                    rs(row["concession_paisa"]),
                    day(row["due_date"]),
                    rs(row["paid_paisa"]),
                    rs(row["remaining_paisa"]),
                ]
                for row in data["charges"]
            ],
            [row["id"] for row in data["charges"]],
            widths=[0, 110, 120, 110, 110, 120],
            visible_rows=4,
        )
        fill_table(
            self.payments,
            ["Voucher", "Amount", "Status", "When", "Clerk"],
            [
                [row["voucher_no"], rs(row["amount_paisa"]), row["status_label"], row["created_at"][:16], row["clerk_name"]]
                for row in data["payments"]
            ],
            [row["id"] for row in data["payments"]],
            widths=[160, 110, 120, 150, 0],
            visible_rows=4,
        )
        fill_table(
            self.adjustments,
            ["When", "Amount", "Reason"],
            [
                [row["created_at"][:16], rs(row["amount_paisa"]), row["reason"]]
                for row in data["adjustments"]
            ],
            [row["id"] for row in data["adjustments"]],
            widths=[160, 120, 0],
            visible_rows=3,
        )

    def _take(self) -> None:
        if self.data is None:
            return
        dialog = PaymentDialog(self, self.data)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        from pics_fee.printing import print_voucher

        voucher = self.call(
            lambda: self.api.request(
                "POST",
                "/payments",
                {"student_id": self.student_id, "amount_rupees": dialog.payload},
            )
        )
        if voucher is None:
            return
        print_voucher(self, voucher)
        self.reload()

    def _package(self) -> None:
        packages = self.call(lambda: self.api.request("GET", "/packages"))
        if packages is None or self.data is None:
            return
        applied = {row.get("source_package_id") for row in self.data["charges"]}
        choices = [
            package
            for package in packages
            if package["class_id"] == self.data["class_id"]
            and package["academic_session_id"] == self.data["academic_session_id"]
            and package["id"] not in applied
        ]
        if not choices:
            warn(self, "There is no further fee package for this class and session.")
            return
        picker = _PackageDialog(self, choices)
        if picker.exec() != QDialog.DialogCode.Accepted or picker.package is None:
            return
        package = picker.package
        result = self.call(
            lambda: self.api.request("POST", f"/students/{self.student_id}/package", {"package_id": package["id"]})
        )
        if result is not None:
            self.reload()

    def _concession(self) -> None:
        if self.data is None:
            return
        charge_id = selected_id(self.charges)
        charge = next((row for row in self.data["charges"] if row["id"] == charge_id), None)
        if charge is None:
            warn(self, "Select a fee head first.")
            return
        dialog = ConcessionDialog(self, charge)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        result = self.call(
            lambda: self.api.request("POST", f"/charges/{charge_id}/concession", dialog.payload)
        )
        if result is not None:
            self.reload()

    def _adjust(self) -> None:
        dialog = AdjustmentDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        result = self.call(
            lambda: self.api.request("POST", f"/students/{self.student_id}/adjustments", dialog.payload)
        )
        if result is not None:
            self.reload()

    def _status(self) -> None:
        if self.data is None:
            return
        status = "active" if self.data["status"] == "left" else "left"
        result = self.call(
            lambda: self.api.request("POST", f"/students/{self.student_id}/status", {"status": status})
        )
        if result is not None:
            self.reload()


def _quote(text: str) -> str:
    from urllib.parse import quote

    return quote(text)
