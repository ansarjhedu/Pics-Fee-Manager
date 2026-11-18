from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QVBoxLayout,
)

from pics_fee.printing import print_voucher
from pics_fee.ui.dialogs import NameDialog, PackageDialog, PaymentDialog, StudentDialog
from pics_fee.ui.pages_students import LedgerDialog
from pics_fee.ui.theme import (
    Page,
    ask,
    block_title,
    button,
    fill_table,
    place_dialog,
    heading,
    inform,
    note,
    page_fill,
    panel,
    toolbar,
    rs,
    selected_id,
    warn,
)


class ClassesPage(Page):
    def __init__(self, api, on_unauthorized, role: str):
        super().__init__(api, on_unauthorized)
        self.role = role
        self._board: list[dict] = []
        self._students: list[dict] = []
        self._class_id = None
        self._section = ""
        root = page_fill(self)
        root.addWidget(heading("Classes"))
        root.addWidget(note("Each class keeps its own sections and students. Open a student for the full fee card."))
        self.session_filter = QComboBox()
        self.session_filter.setMinimumWidth(160)
        self.status_filter = QComboBox()
        self.status_filter.addItem("Active", "active")
        self.status_filter.addItem("Left", "left")
        self.status_filter.addItem("All", "all")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find a student in the selected class")
        self.search.returnPressed.connect(self._load_students)
        find = button("Show", "quiet")
        find.clicked.connect(self._load_students)
        pieces = [self.session_filter, self.status_filter, self.search, find]
        if role == "admin":
            add_class = button("Add class")
            add_class.clicked.connect(self._add_class)
            add_session = button("Add session", "quiet")
            add_session.clicked.connect(self._add_session)
            pieces.extend([add_class, add_session])
        root.addWidget(toolbar(*pieces))

        body = QHBoxLayout()
        body.setSpacing(12)
        self.class_list = QListWidget()
        self.class_list.setFixedWidth(280)
        self.class_list.currentItemChanged.connect(lambda *_args: self._load_students())
        body.addWidget(self.class_list)

        right = QVBoxLayout()
        right.setSpacing(8)
        self.class_title = block_title("Select a class")
        right.addWidget(self.class_title)
        self.section_filter = QComboBox()
        self.section_filter.setMinimumWidth(160)
        self.section_filter.currentIndexChanged.connect(self._apply_section)
        section_pieces = [QLabel("Section"), self.section_filter]
        if role == "admin":
            add_section = button("Add section", "quiet")
            add_section.clicked.connect(self._add_section)
            remove_section = button("Remove section", "danger")
            remove_section.clicked.connect(self._remove_section)
            section_pieces.extend([add_section, remove_section])
        section_pieces.append(None)
        right.addWidget(toolbar(*section_pieces))
        self.summary = note("Choose a class to see its students.")
        right.addWidget(self.summary)
        self.table = QTableWidget()
        self.table.doubleClicked.connect(self._open)
        right.addWidget(self.table, 1)
        add_student = button("Add student")
        add_student.clicked.connect(self._add_student)
        edit = button("Edit", "quiet")
        edit.clicked.connect(self._edit)
        open_card = button("Open card", "quiet")
        open_card.clicked.connect(self._open)
        action_pieces = [add_student, edit, open_card]
        if role == "clerk":
            take = button("Take payment")
            take.clicked.connect(self._take_payment)
            action_pieces.append(take)
        if role == "admin":
            remove = button("Remove", "danger")
            remove.clicked.connect(self._remove)
            action_pieces.append(remove)
        action_pieces.append(None)
        right.addWidget(toolbar(*action_pieces))
        body.addLayout(right, 1)
        root.addLayout(body, 1)
        self.session_filter.currentIndexChanged.connect(self.refresh)
        self.status_filter.currentIndexChanged.connect(self.refresh)

    def refresh(self) -> None:
        sessions = self.call(lambda: self.api.request("GET", "/sessions"))
        if sessions is None:
            return
        current_session = self.session_filter.currentData()
        self.session_filter.blockSignals(True)
        self.session_filter.clear()
        self.session_filter.addItem("All sessions", None)
        for row in sessions:
            self.session_filter.addItem(row["name"], row["id"])
        index = self.session_filter.findData(current_session)
        self.session_filter.setCurrentIndex(index if index >= 0 else 0)
        self.session_filter.blockSignals(False)
        session_id = self.session_filter.currentData()
        status = self.status_filter.currentData()
        query = f"/classes/board?status={status}"
        if session_id:
            query += f"&session_id={session_id}"
        board = self.call(lambda: self.api.request("GET", query))
        if board is None:
            return
        self._board = board
        selected = self._class_id
        self.class_list.blockSignals(True)
        self.class_list.clear()
        for row in board:
            section_count = len([item for item in row["sections"] if item["name"]])
            item = QListWidgetItem(f"{row['name']}\n{row['students']} students · {section_count} sections")
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            item.setSizeHint(QSize(0, 56))
            self.class_list.addItem(item)
            if row["id"] == selected:
                self.class_list.setCurrentItem(item)
        if self.class_list.currentRow() < 0 and self.class_list.count():
            self.class_list.setCurrentRow(0)
        self.class_list.blockSignals(False)
        self._load_students()

    def _selected_class(self) -> dict | None:
        item = self.class_list.currentItem()
        if item is None:
            return None
        class_id = item.data(Qt.ItemDataRole.UserRole)
        self._class_id = class_id
        return next((row for row in self._board if row["id"] == class_id), None)

    def _load_students(self) -> None:
        klass = self._selected_class()
        if klass is None:
            self.class_title.setText("Select a class")
            self.summary.setText("Add a class, then add its sections and students.")
            fill_table(self.table, ["Admission", "Student", "Father", "Section", "Mobile", "Total", "Paid", "Waiting", "Remaining"], [], fit=False)
            return
        self.class_title.setText(klass["name"])
        chosen = self.section_filter.currentData()
        self.section_filter.blockSignals(True)
        self.section_filter.clear()
        self.section_filter.addItem("All sections", "")
        for section in klass["sections"]:
            label = section["name"] or "No section"
            self.section_filter.addItem(f"{label} · {section['students']}", section["name"])
        index = self.section_filter.findData(chosen if chosen is not None else "")
        self.section_filter.setCurrentIndex(index if index >= 0 else 0)
        self.section_filter.blockSignals(False)
        self._section = self.section_filter.currentData() or ""
        params = [f"status={self.status_filter.currentData()}", f"class_id={klass['id']}", f"search={_quote(self.search.text().strip())}"]
        if self.session_filter.currentData():
            params.append(f"session_id={self.session_filter.currentData()}")
        rows = self.call(lambda: self.api.request("GET", "/students?" + "&".join(params)))
        if rows is None:
            return
        self._students = rows
        self._apply_section()

    def _apply_section(self) -> None:
        section = self.section_filter.currentData()
        self._section = section or ""
        rows = self._students
        if section:
            rows = [row for row in rows if (row.get("section") or "") == section]
        waiting = sum(row["waiting_paisa"] for row in rows)
        remaining = sum(row["remaining_paisa"] for row in rows)
        self.summary.setText(f"{len(rows)} student(s) in this view. Waiting {rs(waiting)}. Still to collect {rs(remaining)}.")
        fill_table(
            self.table,
            ["Admission", "Student", "Father", "Section", "Session", "Mobile", "Total", "Paid", "Waiting", "Remaining"],
            [
                [
                    row["admission_no"],
                    row["name"],
                    row["father_name"],
                    row.get("section") or "",
                    row["session_name"],
                    row["phone"],
                    rs(row["total_paisa"]),
                    rs(row["paid_paisa"]),
                    rs(row["waiting_paisa"]),
                    rs(row["remaining_paisa"]),
                ]
                for row in rows
            ],
            [row["id"] for row in rows],
            fit=False,
            widths=[110, 0, 140, 80, 120, 130, 110, 100, 110, 120],
        )
        self._visible = rows

    def _student(self):
        student_id = selected_id(self.table)
        if student_id is None:
            warn(self, "Select a student first.")
            return None
        return next((row for row in self._visible if row["id"] == student_id), None)

    def _catalog(self):
        classes = self.call(lambda: self.api.request("GET", "/classes"))
        sessions = self.call(lambda: self.api.request("GET", "/sessions"))
        packages = self.call(lambda: self.api.request("GET", "/packages"))
        if classes is None or sessions is None or packages is None:
            return None
        return classes, sessions, packages

    def _add_class(self) -> None:
        dialog = NameDialog(self, "Add class", "Class name")
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        if self.call(lambda: self.api.request("POST", "/classes", {"name": dialog.payload})) is not None:
            self.refresh()

    def _add_session(self) -> None:
        dialog = NameDialog(self, "Add session", "Session, for example 2026-2027")
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        if self.call(lambda: self.api.request("POST", "/sessions", {"name": dialog.payload})) is not None:
            self.refresh()

    def _add_section(self) -> None:
        klass = self._selected_class()
        if klass is None:
            warn(self, "Select a class first.")
            return
        dialog = NameDialog(self, f"Section in {klass['name']}", "Section name, for example A")
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        if self.call(lambda: self.api.request("POST", f"/classes/{klass['id']}/sections", {"name": dialog.payload})) is not None:
            self.refresh()

    def _remove_section(self) -> None:
        klass = self._selected_class()
        name = self.section_filter.currentData()
        if klass is None or not name:
            warn(self, "Select a section first.")
            return
        section = next((item for item in klass["sections"] if item["name"] == name and item["id"]), None)
        if section is None:
            warn(self, "This section comes from student records. It stays while students are in it.")
            return
        if not ask(self, f"Remove section {name} from {klass['name']}?"):
            return
        if self.call(lambda: self.api.request("DELETE", f"/sections/{section['id']}")) is not None:
            self.refresh()

    def _add_student(self) -> None:
        catalog = self._catalog()
        klass = self._selected_class()
        if catalog is None:
            return
        dialog = StudentDialog(
            self,
            *catalog,
            class_id=None if klass is None else klass["id"],
            session_id=self.session_filter.currentData(),
            section=self._section,
        )
        if dialog.exec() == dialog.DialogCode.Accepted and self.call(lambda: self.api.request("POST", "/students", dialog.payload)):
            self.refresh()

    def _edit(self) -> None:
        row = self._student()
        catalog = self._catalog()
        if row is None or catalog is None:
            return
        dialog = StudentDialog(self, *catalog, student=row)
        if dialog.exec() == dialog.DialogCode.Accepted and self.call(lambda: self.api.request("PUT", f"/students/{row['id']}", dialog.payload)):
            self.refresh()

    def _take_payment(self) -> None:
        row = self._student()
        if row is None:
            return
        ledger = self.call(lambda: self.api.request("GET", f"/students/{row['id']}"))
        if ledger is None:
            return
        dialog = PaymentDialog(self, ledger)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        voucher = self.call(
            lambda: self.api.request(
                "POST",
                "/payments",
                {"student_id": row["id"], "amount_rupees": dialog.payload},
            )
        )
        if voucher is None:
            return
        inform(self, f"Voucher {voucher['voucher_no']} is in the drawer. Hand the notes over from the Desk.")
        print_voucher(self, voucher)
        self.refresh()

    def _open(self) -> None:
        row = self._student()
        if row is None:
            return
        LedgerDialog(self, self.api, self.on_unauthorized, self.role, row["id"]).exec()
        self.refresh()

    def _remove(self) -> None:
        row = self._student()
        if row is None:
            return
        if not ask(self, f"Remove {row['name']}? A student with fee history stays on record."):
            return
        result = self.call(lambda: self.api.request("DELETE", f"/students/{row['id']}"))
        if result is not None:
            self.refresh()


class FeesPage(Page):
    def __init__(self, api, on_unauthorized):
        super().__init__(api, on_unauthorized)
        self._classes = []
        self._sessions = []
        self._packages = []
        root = page_fill(self)
        root.addWidget(heading("Fees"))
        root.addWidget(
            note(
                "Create a package for a class and session. "
                "Adding students to a package copies those fee heads onto each student, so later package edits do not rewrite them."
            )
        )
        self.class_filter = QComboBox()
        self.session_filter = QComboBox()
        self.class_filter.setMinimumWidth(160)
        self.session_filter.setMinimumWidth(160)
        root.addWidget(toolbar(self.class_filter, self.session_filter, None))
        self.table = QTableWidget()
        root.addWidget(self.table, 1)
        new_package = button("New package")
        new_package.clicked.connect(self._add_package)
        edit = button("Edit", "quiet")
        edit.clicked.connect(self._edit_package)
        remove = button("Remove", "danger")
        remove.clicked.connect(self._remove_package)
        enroll = button("Add students to package")
        enroll.clicked.connect(self._enroll)
        root.addWidget(toolbar(new_package, edit, enroll, remove, None))
        self.class_filter.currentIndexChanged.connect(self._show_packages)
        self.session_filter.currentIndexChanged.connect(self._show_packages)

    def refresh(self) -> None:
        classes = self.call(lambda: self.api.request("GET", "/classes"))
        sessions = self.call(lambda: self.api.request("GET", "/sessions"))
        packages = self.call(lambda: self.api.request("GET", "/packages"))
        if classes is None or sessions is None or packages is None:
            return
        self._classes, self._sessions, self._packages = classes, sessions, packages
        self._fill_filter(self.class_filter, "All classes", classes)
        self._fill_filter(self.session_filter, "All sessions", sessions)
        self._show_packages()

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

    def _visible_packages(self) -> list[dict]:
        class_id = self.class_filter.currentData()
        session_id = self.session_filter.currentData()
        rows = self._packages
        if class_id:
            rows = [row for row in rows if row["class_id"] == class_id]
        if session_id:
            rows = [row for row in rows if row["academic_session_id"] == session_id]
        return rows

    def _show_packages(self) -> None:
        rows = self._visible_packages()
        fill_table(
            self.table,
            ["Package", "Class", "Session", "Heads", "Amount"],
            [
                [
                    row["name"],
                    row["class_name"],
                    row["session_name"],
                    ", ".join(item["head_name"] for item in row["items"]),
                    rs(sum(item["amount_paisa"] for item in row["items"])),
                ]
                for row in rows
            ],
            [row["id"] for row in rows],
            fit=False,
            widths=[180, 120, 140, 0, 120],
        )

    def _selected_package(self):
        package_id = selected_id(self.table)
        package = next((row for row in self._packages if row["id"] == package_id), None)
        if package is None:
            warn(self, "Select a fee package first.")
        return package

    def _add_package(self) -> None:
        if not self._classes or not self._sessions:
            warn(self, "Add a class and a session on the Classes page first.")
            return
        dialog = PackageDialog(self, self._classes, self._sessions)
        if dialog.exec() == dialog.DialogCode.Accepted and self.call(lambda: self.api.request("POST", "/packages", dialog.payload)):
            self.refresh()

    def _edit_package(self) -> None:
        package = self._selected_package()
        if package is None:
            return
        dialog = PackageDialog(self, self._classes, self._sessions, package)
        if dialog.exec() == dialog.DialogCode.Accepted and self.call(
            lambda: self.api.request("PUT", f"/packages/{package['id']}", dialog.payload)
        ):
            self.refresh()

    def _remove_package(self) -> None:
        package = self._selected_package()
        if package is None:
            return
        if not ask(self, "Remove this fee package? Students who already have it keep their copy."):
            return
        if self.call(lambda: self.api.request("DELETE", f"/packages/{package['id']}")) is not None:
            self.refresh()

    def _enroll(self) -> None:
        package = self._selected_package()
        if package is None:
            return
        students = self.call(
            lambda: self.api.request(
                "GET",
                f"/students?class_id={package['class_id']}&session_id={package['academic_session_id']}&status=all",
            )
        )
        if students is None:
            return
        if not students:
            warn(self, "This class and session have no students yet. Add them on the Classes page.")
            return
        dialog = _EnrollDialog(self, students, package["name"])
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        added = 0
        skipped = []
        for student_id in dialog.chosen:
            result = self.call(
                lambda student_id=student_id: self.api.request(
                    "POST",
                    f"/students/{student_id}/package",
                    {"package_id": package["id"]},
                )
            )
            if result is None:
                skipped.append(student_id)
            else:
                added += 1
        inform(
            self,
            f"Package added to {added} student(s)." + (f" {len(skipped)} could not be updated." if skipped else ""),
        )
        self.refresh()


class _EnrollDialog(QDialog):
    def __init__(self, parent, students: list[dict], package_name: str):
        super().__init__(parent)
        self.setWindowTitle("Add students to package")
        self.chosen: list[int] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)
        root.addWidget(block_title(package_name))
        root.addWidget(note("Select the students who should receive this package. Hold Ctrl to select more than one."))
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        for row in students:
            item = QListWidgetItem(f"{row['admission_no']}  {row['name']}  ·  {row.get('section') or ''}")
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.list.addItem(item)
        root.addWidget(self.list, 1)
        buttons = QHBoxLayout()
        ok = button("Add to selected students")
        cancel = button("Cancel", "quiet")
        ok.clicked.connect(self._accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        buttons.addStretch(1)
        root.addLayout(buttons)
        place_dialog(self, 520, 520)

    def _accept(self) -> None:
        self.chosen = [item.data(Qt.ItemDataRole.UserRole) for item in self.list.selectedItems()]
        if not self.chosen:
            warn(self, "Select at least one student.")
            return
        self.accept()


def _quote(text: str) -> str:
    from urllib.parse import quote

    return quote(text)
