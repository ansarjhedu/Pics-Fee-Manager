from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pics_fee.ui.theme import button, place_dialog, rs, warn


def _quiet(box: QDialogButtonBox) -> None:
    cancel = box.button(QDialogButtonBox.StandardButton.Cancel)
    if cancel is None:
        return
    cancel.setProperty("kind", "quiet")
    cancel.style().unpolish(cancel)
    cancel.style().polish(cancel)


class _FormDialog(QDialog):
    def __init__(self, parent, title: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.payload = None
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        host.setMinimumWidth(0)
        self.form = QFormLayout(host)
        self.form.setContentsMargins(0, 0, 4, 0)
        self.form.setHorizontalSpacing(12)
        self.form.setVerticalSpacing(8)
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        scroll.setWidget(host)
        root.addWidget(scroll, 1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self._submit)
        self.buttons.rejected.connect(self.reject)
        _quiet(self.buttons)
        root.addWidget(self.buttons)

    def _submit(self) -> None:
        payload = self.build_payload()
        if payload is None:
            return
        self.payload = payload
        self.accept()

    def build_payload(self):
        return None


def _line(text: str = "", secret: bool = False) -> QLineEdit:
    widget = QLineEdit(text)
    if secret:
        widget.setEchoMode(QLineEdit.EchoMode.Password)
    return widget


class ClerkDialog(_FormDialog):
    def __init__(self, parent):
        super().__init__(parent, "New clerk")
        self.display = _line()
        self.username = _line()
        self.password = _line(secret=True)
        self.confirm = _line(secret=True)
        self.form.addRow("Name", self.display)
        self.form.addRow("Username", self.username)
        self.form.addRow("Password", self.password)
        self.form.addRow("Confirm password", self.confirm)
        place_dialog(self, 460, 460)

    def build_payload(self):
        if self.password.text() != self.confirm.text():
            warn(self, "The two passwords do not match.")
            return None
        return {
            "display_name": self.display.text().strip(),
            "username": self.username.text().strip(),
            "password": self.password.text(),
        }


class PasswordDialog(_FormDialog):
    def __init__(self, parent, title: str):
        super().__init__(parent, title)
        self.password = _line(secret=True)
        self.confirm = _line(secret=True)
        self.form.addRow("New password", self.password)
        self.form.addRow("Confirm password", self.confirm)
        place_dialog(self, 440, 320)

    def build_payload(self):
        if self.password.text() != self.confirm.text():
            warn(self, "The two passwords do not match.")
            return None
        return self.password.text()


class NameDialog(_FormDialog):
    def __init__(self, parent, title: str, label: str):
        super().__init__(parent, title)
        self.name = _line()
        self.form.addRow(label, self.name)
        place_dialog(self, 440, 260)

    def build_payload(self):
        if not self.name.text().strip():
            warn(self, "Enter a name.")
            return None
        return self.name.text().strip()


class StudentDialog(_FormDialog):
    def __init__(self, parent, classes, sessions, packages, student=None, class_id=None, session_id=None, section=""):
        super().__init__(parent, "Edit student" if student else "Add student")
        self.packages = packages
        self.editing = student is not None
        self.admission = _line("" if student is None else student["admission_no"])
        self.name = _line("" if student is None else student["name"])
        self.father = _line("" if student is None else student["father_name"])
        self.section = _line("" if student is None else student.get("section") or "")
        self.phone = _line("" if student is None else student["phone"])
        self.class_box = QComboBox()
        self.session_box = QComboBox()
        for row in classes:
            self.class_box.addItem(row["name"], row["id"])
        for row in sessions:
            self.session_box.addItem(row["name"], row["id"])
        if student is not None:
            self._select(self.class_box, student["class_id"])
            self._select(self.session_box, student["academic_session_id"])
        self.form.addRow("Admission no.", self.admission)
        self.form.addRow("Student name", self.name)
        self.form.addRow("Father name", self.father)
        self.form.addRow("Class", self.class_box)
        self.form.addRow("Section", self.section)
        self.form.addRow("Session", self.session_box)
        self.form.addRow("Guardian mobile", self.phone)
        self.apply_box = QCheckBox("Apply this fee package")
        self.package_box = QComboBox()
        if student is None:
            self.class_box.currentIndexChanged.connect(self._fill_packages)
            self.session_box.currentIndexChanged.connect(self._fill_packages)
            if class_id:
                self._select(self.class_box, class_id)
            if session_id:
                self._select(self.session_box, session_id)
            if section:
                self.section.setText(section)
            self._fill_packages()
            self.form.addRow("Fee package", self.package_box)
            self.form.addRow(self.apply_box)
            self.apply_box.setChecked(self.package_box.count() > 0)
        else:
            note = QLabel("Class and session stay fixed after a fee package is on the record.")
            note.setWordWrap(True)
            note.setObjectName("muted")
            self.form.addRow(note)
        place_dialog(self, 520, 640)

    def _select(self, box: QComboBox, value) -> None:
        index = box.findData(value)
        if index >= 0:
            box.setCurrentIndex(index)

    def _fill_packages(self) -> None:
        class_id = self.class_box.currentData()
        session_id = self.session_box.currentData()
        self.package_box.clear()
        for package in self.packages:
            if package["class_id"] == class_id and package["academic_session_id"] == session_id:
                self.package_box.addItem(package["name"], package["id"])
        self.apply_box.setEnabled(self.package_box.count() > 0)

    def build_payload(self):
        if self.class_box.currentData() is None or self.session_box.currentData() is None:
            warn(self, "Add a class and a session before entering students.")
            return None
        payload = {
            "admission_no": self.admission.text().strip(),
            "name": self.name.text().strip(),
            "father_name": self.father.text().strip(),
            "class_id": self.class_box.currentData(),
            "section": self.section.text().strip(),
            "academic_session_id": self.session_box.currentData(),
            "phone": self.phone.text().strip(),
        }
        if not self.editing and self.apply_box.isChecked() and self.package_box.currentData() is not None:
            payload["package_id"] = self.package_box.currentData()
        return payload


class PaymentDialog(_FormDialog):
    def __init__(self, parent, student: dict):
        super().__init__(parent, "Take fee")
        self.student = student
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText("Save and print voucher")
        who = QLabel(student["name"])
        who.setObjectName("section")
        who.setWordWrap(True)
        detail = QLabel(
            f"Admission {student['admission_no']}"
            + (f"  ·  {student['class_name']} {student.get('section') or ''}".rstrip() if student.get("class_name") else "")
        )
        detail.setObjectName("muted")
        detail.setWordWrap(True)
        self.form.addRow(who)
        self.form.addRow(detail)
        figures = QWidget()
        grid = QGridLayout(figures)
        grid.setContentsMargins(0, 4, 0, 4)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)
        for index, (caption, key) in enumerate(
            (("Total", "total_paisa"), ("Paid", "paid_paisa"), ("Waiting", "waiting_paisa"), ("Remaining", "remaining_paisa"))
        ):
            cap = QLabel(caption)
            cap.setObjectName("muted")
            value = QLabel(rs(student[key]))
            value.setObjectName("blockTitle")
            value.setWordWrap(True)
            value.setMinimumWidth(0)
            value.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            grid.addWidget(cap, 0, index)
            grid.addWidget(value, 1, index)
            grid.setColumnStretch(index, 1)
        self.form.addRow(figures)
        self.amount = _line()
        self.amount.setPlaceholderText("Rupees received")
        self.preview = QLabel("Enter the cash received.")
        self.preview.setObjectName("muted")
        self.preview.setWordWrap(True)
        self.amount.textChanged.connect(self._preview)
        self.form.addRow("Cash received", self.amount)
        self.form.addRow(self.preview)
        place_dialog(self, 520, 460)
        if student.get("collectable_paisa", 0) <= 0:
            self.amount.setEnabled(False)
            self.preview.setText("There is no fee left to collect.")

    def _preview(self) -> None:
        text = self.amount.text().strip().replace(",", "")
        if not text.isdigit():
            self.preview.setText("Enter whole rupees.")
            return
        paisa = int(text) * 100
        left = self.student["collectable_paisa"] - paisa
        if left < 0:
            self.preview.setText(f"That is more than the remaining fee ({rs(self.student['collectable_paisa'])}).")
            return
        self.preview.setText(f"Remaining after this voucher: {rs(left)}")

    def build_payload(self):
        text = self.amount.text().strip().replace(",", "")
        if not text.isdigit() or int(text) <= 0:
            warn(self, "Enter the cash received in whole rupees.")
            return None
        return int(text)


class PackageDialog(QDialog):
    def __init__(self, parent, classes, sessions, package=None):
        super().__init__(parent)
        self.setWindowTitle("Edit fee package" if package else "New fee package")
        self.payload = None
        self.rows: list[tuple] = []
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.name = _line("" if package is None else package["name"])
        self.class_box = QComboBox()
        self.session_box = QComboBox()
        for row in classes:
            self.class_box.addItem(row["name"], row["id"])
        for row in sessions:
            self.session_box.addItem(row["name"], row["id"])
        if package is not None:
            index = self.class_box.findData(package["class_id"])
            if index >= 0:
                self.class_box.setCurrentIndex(index)
            index = self.session_box.findData(package["academic_session_id"])
            if index >= 0:
                self.session_box.setCurrentIndex(index)
        form.addRow("Package name", self.name)
        form.addRow("Class", self.class_box)
        form.addRow("Session", self.session_box)
        root.addLayout(form)
        note = QLabel("Changing a package does not change students who already have it.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        root.addWidget(note)
        self.item_host = QVBoxLayout()
        holder = QWidget()
        holder.setLayout(self.item_host)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        root.addWidget(scroll, 1)
        root.addWidget(button("Add fee head", "quiet"))
        root.itemAt(root.count() - 1).widget().clicked.connect(lambda: self._add_row())
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        _quiet(buttons)
        root.addWidget(buttons)
        items = [] if package is None else package.get("items") or []
        if items:
            for item in items:
                self._add_row(item["head_name"], str(item["amount_paisa"] // 100), item["due_date"])
        else:
            self._add_row()
        place_dialog(self, 760, 560)

    def _add_row(self, head: str = "", amount: str = "", due: str | None = None) -> None:
        line = QHBoxLayout()
        head_box = _line(head)
        head_box.setPlaceholderText("Fee head, for example Tuition")
        amount_box = _line(amount)
        amount_box.setPlaceholderText("Rupees")
        due_box = QDateEdit()
        due_box.setCalendarPopup(True)
        due_box.setDisplayFormat("dd MMM yyyy")
        if due:
            due_box.setDate(QDate.fromString(due, "yyyy-MM-dd"))
        else:
            due_box.setDate(QDate.currentDate())
        remove = button("Remove", "quiet")
        line.addWidget(head_box, 2)
        line.addWidget(amount_box, 1)
        line.addWidget(due_box, 1)
        line.addWidget(remove)
        self.item_host.addLayout(line)
        entry = (line, head_box, amount_box, due_box)
        self.rows.append(entry)
        remove.clicked.connect(lambda: self._remove_row(entry))

    def _remove_row(self, entry) -> None:
        if entry not in self.rows:
            return
        self.rows.remove(entry)
        line = entry[0]
        while line.count():
            child = line.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.item_host.removeItem(line)

    def _submit(self) -> None:
        items = []
        for _line, head_box, amount_box, due_box in self.rows:
            head = head_box.text().strip()
            amount = amount_box.text().strip().replace(",", "")
            if not head and not amount:
                continue
            if not head or not amount.isdigit() or int(amount) <= 0:
                warn(self, "Each fee head needs a name and an amount in whole rupees.")
                return
            items.append(
                {
                    "head_name": head,
                    "amount_rupees": int(amount),
                    "due_date": due_box.date().toString("yyyy-MM-dd"),
                }
            )
        if not items:
            warn(self, "Add at least one fee head.")
            return
        if self.class_box.currentData() is None or self.session_box.currentData() is None:
            warn(self, "Add a class and a session first.")
            return
        self.payload = {
            "name": self.name.text().strip(),
            "class_id": self.class_box.currentData(),
            "academic_session_id": self.session_box.currentData(),
            "items": items,
        }
        self.accept()


class ConcessionDialog(_FormDialog):
    def __init__(self, parent, charge: dict):
        super().__init__(parent, "Concession")
        self.charge = charge
        note = QLabel(
            f"{charge['head_name']}: {rs(charge['amount_paisa'])}. "
            f"Current concession {rs(charge['concession_paisa'])}."
        )
        note.setWordWrap(True)
        self.form.addRow(note)
        self.amount = _line(str(charge["concession_paisa"] // 100))
        self.reason = _line(charge.get("concession_reason") or "")
        self.form.addRow("Concession (rupees)", self.amount)
        self.form.addRow("Reason", self.reason)
        place_dialog(self, 480, 380)

    def build_payload(self):
        text = self.amount.text().strip().replace(",", "")
        if not text.isdigit():
            warn(self, "Enter the concession in whole rupees. Use 0 to clear it.")
            return None
        if not self.reason.text().strip():
            warn(self, "Write the reason for this concession.")
            return None
        return {"amount_rupees": int(text), "reason": self.reason.text().strip()}


class AdjustmentDialog(_FormDialog):
    def __init__(self, parent):
        super().__init__(parent, "Correction")
        self.direction = QComboBox()
        self.direction.addItem("Reduce what the student owes", "credit")
        self.direction.addItem("Increase what the student owes", "reverse")
        self.amount = _line()
        self.reason = _line()
        self.form.addRow("Correction", self.direction)
        self.form.addRow("Rupees", self.amount)
        self.form.addRow("Reason", self.reason)
        place_dialog(self, 480, 400)

    def build_payload(self):
        text = self.amount.text().strip().replace(",", "")
        if not text.isdigit() or int(text) <= 0:
            warn(self, "Enter the correction in whole rupees.")
            return None
        if not self.reason.text().strip():
            warn(self, "Write the reason for this correction.")
            return None
        return {
            "direction": self.direction.currentData(),
            "amount_rupees": int(text),
            "reason": self.reason.text().strip(),
        }


class FixVoucherDialog(_FormDialog):
    def __init__(self, parent, row: dict):
        super().__init__(parent, "Correct voucher")
        title = QLabel(row["voucher_no"])
        title.setObjectName("section")
        title.setWordWrap(True)
        reason = QLabel(row.get("reject_reason") or "The principal sent this voucher back.")
        reason.setWordWrap(True)
        reason.setObjectName("muted")
        previous = QLabel(f"Previous amount {rs(row['amount_paisa'])}")
        previous.setObjectName("blockTitle")
        self.form.addRow(title)
        self.form.addRow(reason)
        self.form.addRow(previous)
        self.amount = _line(str(row["amount_paisa"] // 100))
        self.form.addRow("Correct cash amount", self.amount)
        place_dialog(self, 480, 420)

    def build_payload(self):
        text = self.amount.text().strip().replace(",", "")
        if not text.isdigit() or int(text) <= 0:
            warn(self, "Enter the corrected amount in whole rupees.")
            return None
        return int(text)
