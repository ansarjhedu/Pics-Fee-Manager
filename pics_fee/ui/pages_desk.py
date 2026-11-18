from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from pics_fee.printing import print_handover, print_voucher
from pics_fee.textfmt import format_rs
from pics_fee.ui.dialogs import FixVoucherDialog, PaymentDialog
from pics_fee.ui.theme import (
    Page,
    ask,
    block_title,
    button,
    card,
    fill_table,
    guide,
    heading,
    panel,
    inform,
    mount_page,
    page_fill,
    note,
    rs,
    selected_id,
    warn,
    when,
)


def _desk_block(title: str, table: QTableWidget, actions: list) -> QWidget:
    box = panel()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(14)
    layout.addWidget(block_title(title))
    table.setMinimumHeight(148)
    layout.addWidget(table)
    row = QHBoxLayout()
    row.setContentsMargins(0, 6, 0, 0)
    row.setSpacing(16)
    for widget in actions:
        widget.setMinimumHeight(40)
        row.addWidget(widget)
    row.addStretch(1)
    layout.addLayout(row)
    return box


class ClerkDesk(Page):
    def __init__(self, api, on_unauthorized):
        super().__init__(api, on_unauthorized)
        root = mount_page(self)
        root.addWidget(heading("Fee desk"))
        root.addWidget(note("Find the student, record the cash, then hand the notes to the principal."))
        search_row = QHBoxLayout()
        search_row.setSpacing(12)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Name, father, admission number, or mobile")
        self.search.returnPressed.connect(self._search)
        search_row.addWidget(self.search, 1)
        find = button("Find", "quiet")
        find.clicked.connect(self._search)
        take = button("Take payment")
        take.clicked.connect(self._take_from_results)
        search_row.addWidget(find)
        search_row.addWidget(take)
        root.addLayout(search_row)
        self.results = QTableWidget()
        self.results.doubleClicked.connect(self._take_from_results)
        fill_table(self.results, ["Admission", "Student", "Class", "Section", "Remaining"], [], widths=[110, 0, 90, 80, 120])
        root.addWidget(self.results)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        drawer, self.drawer_value = card("In your drawer", "Rs 0", "warn")
        handed, self.handed_value = card("Handed over", "Rs 0", "info")
        sent_back, self.sent_back_value = card("Sent back", "Rs 0")
        cards.addWidget(drawer)
        cards.addWidget(handed)
        cards.addWidget(sent_back)
        root.addLayout(cards)

        root.addWidget(block_title("In the drawer"))
        self.drawer_table = QTableWidget()
        root.addWidget(self.drawer_table)
        actions = panel()
        action_layout = QHBoxLayout(actions)
        action_layout.setContentsMargins(16, 16, 16, 16)
        action_layout.setSpacing(16)
        self.submit_button = button("Submit cash to principal")
        self.submit_button.clicked.connect(self._submit)
        reprint = button("Print voucher", "quiet")
        reprint.clicked.connect(lambda: self._print_selected(self.drawer_table))
        cancel = button("Cancel voucher", "danger")
        cancel.clicked.connect(self._cancel_drawer)
        steps = button("Next step", "quiet")
        steps.clicked.connect(self._explain)
        for widget in (self.submit_button, reprint, cancel, steps):
            widget.setMinimumHeight(40)
            action_layout.addWidget(widget)
        action_layout.addStretch(1)
        root.addWidget(actions)

        self.rejected_table = QTableWidget()
        fix = button("Correct and put back", "quiet")
        fix.clicked.connect(self._fix)
        drop = button("Cancel voucher", "danger")
        drop.clicked.connect(self._cancel_rejected)
        root.addWidget(_desk_block("Sent back by the principal", self.rejected_table, [fix, drop]))

        self.bundle_table = QTableWidget()
        sheet = button("Print handover sheet", "quiet")
        sheet.clicked.connect(self._print_sheet)
        root.addWidget(_desk_block("Handover sheets still open", self.bundle_table, [sheet]))
        self._desk = None

    def _explain(self) -> None:
        guide(
            self,
            "How to hand cash over",
            "1. Find the student and press Take payment.\n"
            "2. Print the voucher and keep the notes with it.\n"
            "3. When the notes are ready, press Submit cash to principal.\n"
            "4. Print the handover sheet and take it with the cash.\n\n"
            "The fee is not paid until the principal counts the notes and approves them.",
        )

    def _heading(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("section")
        return label

    def refresh(self) -> None:
        desk = self.call(lambda: self.api.request("GET", "/desk"))
        if desk is None:
            return
        self._desk = desk
        drawer = desk["unsubmitted"]
        handed = desk["submitted"]
        self.drawer_value.setText(rs(drawer["total_paisa"]))
        self.handed_value.setText(rs(handed["total_paisa"]))
        self.sent_back_value.setText(rs(desk["rejected"]["total_paisa"]))
        self.submit_button.setEnabled(drawer["count"] > 0)
        self._fill_payments(self.drawer_table, drawer["rows"])
        self._fill_payments(self.rejected_table, desk["rejected"]["rows"], with_reason=True)
        bundles = desk["open_submissions"]
        fill_table(
            self.bundle_table,
            ["When", "Vouchers", "Students", "System total"],
            [
                [
                    when(item["submitted_at"]),
                    str(item["voucher_count"]),
                    str(item["student_count"]),
                    rs(item["expected_paisa"]),
                ]
                for item in bundles
            ],
            [item["id"] for item in bundles],
        )

    def _fill_payments(self, table, rows, with_reason: bool = False, fit: bool = True) -> None:
        headers = ["Voucher", "Student", "Class", "Amount"]
        widths = [170, 0, 90, 110]
        if with_reason:
            headers.append("Reason")
            widths = [150, 0, 80, 100, 160]
        body = []
        for row in rows:
            line = [row["voucher_no"], row["student_name"], row["class_name"], rs(row["amount_paisa"])]
            if with_reason:
                line.append(row.get("reject_reason") or "")
            body.append(line)
        fill_table(table, headers, body, [row["id"] for row in rows], fit=fit, widths=widths)

    def _search(self) -> None:
        text = self.search.text().strip()
        rows = self.call(lambda: self.api.request("GET", f"/students?search={_query(text)}&status=active"))
        if rows is None:
            return
        fill_table(
            self.results,
            ["Admission", "Student", "Class", "Section", "Remaining"],
            [
                [row["admission_no"], row["name"], row["class_name"], row.get("section") or "", rs(row["remaining_paisa"])]
                for row in rows
            ],
            [row["id"] for row in rows],
            widths=[110, 0, 90, 80, 120],
        )

    def _take_from_results(self) -> None:
        student_id = selected_id(self.results)
        if student_id is None:
            warn(self, "Select a student first.")
            return
        self._take(student_id)

    def _take(self, student_id: int) -> None:
        ledger = self.call(lambda: self.api.request("GET", f"/students/{student_id}"))
        if ledger is None:
            return
        dialog = PaymentDialog(self, ledger)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        voucher = self.call(
            lambda: self.api.request(
                "POST",
                "/payments",
                {"student_id": student_id, "amount_rupees": dialog.payload},
            )
        )
        if voucher is None:
            return
        inform(self, f"Voucher {voucher['voucher_no']} is in the drawer. It is not paid until the principal approves it.")
        print_voucher(self, voucher)
        self.refresh()

    def _print_selected(self, table) -> None:
        payment_id = selected_id(table)
        if payment_id is None:
            warn(self, "Select a voucher first.")
            return
        voucher = self.call(lambda: self.api.request("GET", f"/payments/{payment_id}"))
        if voucher:
            print_voucher(self, voucher)

    def _cancel_drawer(self) -> None:
        self._cancel(self.drawer_table)

    def _cancel_rejected(self) -> None:
        self._cancel(self.rejected_table)

    def _cancel(self, table) -> None:
        payment_id = selected_id(table)
        if payment_id is None:
            warn(self, "Select a voucher first.")
            return
        if not ask(self, "Cancel this voucher? It will not count as paid."):
            return
        result = self.call(lambda: self.api.request("POST", f"/payments/{payment_id}/cancel"))
        if result is not None:
            self.refresh()

    def _fix(self) -> None:
        payment_id = selected_id(self.rejected_table)
        if payment_id is None or self._desk is None:
            warn(self, "Select a voucher the principal sent back.")
            return
        row = next((item for item in self._desk["rejected"]["rows"] if item["id"] == payment_id), None)
        if row is None:
            return
        dialog = FixVoucherDialog(self, row)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        result = self.call(
            lambda: self.api.request("POST", f"/payments/{payment_id}/revise", {"amount_rupees": dialog.payload})
        )
        if result is not None:
            inform(self, "The voucher is back in the drawer. Print it again if the amount changed.")
            self.refresh()

    def _submit(self) -> None:
        if not ask(self, "Hand these vouchers and the cash to the principal? You will not be able to change them after this."):
            return
        bundle = self.call(lambda: self.api.request("POST", "/submissions"))
        if bundle is None:
            return
        inform(self, "Print the handover sheet and take it with the cash.")
        print_handover(self, bundle)
        self.refresh()

    def _print_sheet(self) -> None:
        submission_id = selected_id(self.bundle_table)
        if submission_id is None:
            warn(self, "Select a handover sheet first.")
            return
        bundle = self.call(lambda: self.api.request("GET", f"/submissions/{submission_id}"))
        if bundle:
            print_handover(self, bundle)


class ApprovalPage(Page):
    def __init__(self, api, on_unauthorized):
        super().__init__(api, on_unauthorized)
        root = mount_page(self)
        root.addWidget(heading("Cash waiting"))
        root.addWidget(
            note(
                "Cash appears here as soon as a clerk records it. "
                "Count and approve it only after the notes are in your hand."
            )
        )
        stats = QHBoxLayout()
        stats.setSpacing(12)
        ready, self.ready_value = card("Ready to count", "Rs 0", "good")
        drawer, self.drawer_value = card("Still with the clerk", "Rs 0", "warn")
        vouchers, self.voucher_value = card("Handed over", "0", "info")
        stats.addWidget(ready)
        stats.addWidget(drawer)
        stats.addWidget(vouchers)
        root.addLayout(stats)

        self.empty = panel()
        empty_layout = QVBoxLayout(self.empty)
        empty_layout.setContentsMargins(22, 20, 22, 20)
        empty_title = QLabel("Nothing is waiting right now")
        empty_title.setObjectName("blockTitle")
        empty_layout.addWidget(empty_title)
        empty_layout.addWidget(
            note("When a clerk records a fee, the voucher shows on this page before the notes are handed over.")
        )
        root.addWidget(self.empty)

        self.drawer_panel = panel("notice", expand=True)
        drawer_layout = QVBoxLayout(self.drawer_panel)
        drawer_layout.setContentsMargins(18, 16, 18, 16)
        drawer_layout.setSpacing(10)
        drawer_layout.addWidget(block_title("Recorded, still with the clerk"))
        self.drawer_note = note(
            "These vouchers are saved, but the clerk has not handed you the notes yet. "
            "Ask the clerk to press Submit cash to principal when the money is in your hand."
        )
        drawer_layout.addWidget(self.drawer_note)
        self.drawer_table = QTableWidget()
        drawer_layout.addWidget(self.drawer_table, 1)
        root.addWidget(self.drawer_panel, 1)

        self.panel = panel()
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(18, 16, 18, 18)
        panel_layout.setSpacing(14)
        panel_layout.addWidget(block_title("Ready for you to count"))
        self.picker = QComboBox()
        self.picker.currentIndexChanged.connect(self._show_selected)
        panel_layout.addWidget(self.picker)
        self.meta = QLabel("")
        self.meta.setObjectName("muted")
        self.meta.setWordWrap(True)
        panel_layout.addWidget(self.meta)
        bundle_stats = QHBoxLayout()
        bundle_stats.setSpacing(12)
        students, self.students_value = card("Students")
        system, self.system_value = card("System total", "Rs 0", "info")
        bundle_stats.addWidget(students)
        bundle_stats.addWidget(system)
        panel_layout.addLayout(bundle_stats)
        counted_title = block_title("Counted cash")
        counted_title.setContentsMargins(0, 6, 0, 0)
        panel_layout.addWidget(counted_title)
        self.counted = QLineEdit()
        self.counted.setPlaceholderText("Type the rupees you counted, for example 5000")
        self.counted.textChanged.connect(self._difference)
        panel_layout.addWidget(self.counted)
        self.difference = QLabel("Enter the cash you counted.")
        self.difference.setObjectName("muted")
        self.difference.setWordWrap(True)
        panel_layout.addWidget(self.difference)
        panel_layout.addWidget(block_title("Vouchers in this handover"))
        self.table = QTableWidget()
        panel_layout.addWidget(self.table)
        root.addWidget(self.panel)
        actions = panel()
        action_layout = QHBoxLayout(actions)
        action_layout.setContentsMargins(14, 12, 14, 12)
        action_layout.setSpacing(12)
        self.approve_all = button("Approve all")
        self.approve_all.clicked.connect(self._approve_all)
        approve_one = button("Approve selected", "quiet")
        approve_one.clicked.connect(self._approve_one)
        reject_one = button("Send back", "danger")
        reject_one.clicked.connect(self._reject_one)
        steps = button("Next step", "quiet")
        steps.clicked.connect(self._explain)
        action_layout.addWidget(self.approve_all)
        action_layout.addWidget(approve_one)
        action_layout.addWidget(reject_one)
        action_layout.addWidget(steps)
        action_layout.addStretch(1)
        root.addWidget(actions)
        self._bundles: list[dict] = []

    def refresh(self) -> None:
        overview = self.call(lambda: self.api.request("GET", "/cash-waiting"))
        if overview is None:
            return
        bundles = overview["ready"]
        self._bundles = bundles
        self.ready_value.setText(rs(overview["ready_total_paisa"]))
        self.drawer_value.setText(rs(overview["with_clerk_total_paisa"]))
        self.voucher_value.setText(str(overview["ready_vouchers"]))
        with_clerk = overview["with_clerk"]
        self.drawer_note.setText(
            f"{overview['with_clerk_count']} voucher(s), {rs(overview['with_clerk_total_paisa'])}. "
            "The clerk still has these notes. Ask them to press Submit cash to principal when the money is in your hand."
        )
        fill_table(
            self.drawer_table,
            ["When", "Clerk", "Voucher", "Student", "Class", "Amount"],
            [
                [
                    when(row["created_at"]),
                    row["clerk_name"],
                    row["voucher_no"],
                    row["student_name"],
                    row["class_name"],
                    rs(row["amount_paisa"]),
                ]
                for row in with_clerk
            ],
            [row["id"] for row in with_clerk],
            fit=False,
            widths=[180, 120, 180, 0, 90, 120],
        )
        self.picker.blockSignals(True)
        self.picker.clear()
        for bundle in bundles:
            self.picker.addItem(
                f"{bundle['clerk_name']}  ·  {when(bundle['submitted_at'])}  ·  {rs(bundle['expected_paisa'])}",
                bundle["id"],
            )
        self.picker.blockSignals(False)
        self.picker.setVisible(len(bundles) > 1)
        self.empty.setVisible(not bundles and not with_clerk)
        self.drawer_panel.setVisible(bool(with_clerk))
        self.panel.setVisible(bool(bundles))
        if bundles:
            self._show_selected()

    def _current(self) -> dict | None:
        bundle_id = self.picker.currentData()
        for bundle in self._bundles:
            if bundle["id"] == bundle_id:
                return bundle
        return None

    def _show_selected(self) -> None:
        bundle = self._current()
        if bundle is None:
            return
        self.meta.setText(f"{bundle['clerk_name']} handed this over on {when(bundle['submitted_at'])}.")
        self.students_value.setText(str(bundle["student_count"]))
        self.system_value.setText(rs(bundle["expected_paisa"]))
        if bundle["counted_paisa"] is None:
            self.counted.clear()
        else:
            self.counted.setText(str(bundle["counted_paisa"] // 100))
        self._difference()
        fill_table(
            self.table,
            ["Voucher", "Student", "Class", "Amount", "Status"],
            [
                [
                    line["voucher_no"],
                    line["student_name"],
                    line["class_name"],
                    rs(line["amount_paisa"]),
                    line["status_label"],
                ]
                for line in bundle["lines"]
            ],
            [line["id"] for line in bundle["lines"]],
            visible_rows=5,
        )

    def _typed_paisa(self):
        text = self.counted.text().strip().replace(",", "").replace(" ", "")
        if not text.isdigit():
            return None
        return int(text) * 100

    def _explain(self) -> None:
        guide(
            self,
            "How this cash is approved",
            "1. The clerk records the fee and prints the voucher.\n"
            "2. The clerk brings you the notes and presses Submit cash to principal.\n"
            "3. Count the notes on this page.\n"
            "4. When the counted amount matches, press Approve all.\n\n"
            "A voucher still with the clerk can be seen here. It cannot be approved until the notes are in your hand.",
        )

    def _difference(self) -> None:
        bundle = self._current()
        if bundle is None:
            self.difference.setText("Type the counted amount after the clerk has handed the cash over.")
            self.difference.setObjectName("muted")
            self.approve_all.setEnabled(True)
            self.difference.style().unpolish(self.difference)
            self.difference.style().polish(self.difference)
            return
        counted = self._typed_paisa()
        if counted is None:
            self.difference.setText("Enter the cash you counted.")
            self.difference.setObjectName("muted")
            self.approve_all.setEnabled(False)
        else:
            gap = counted - bundle["expected_paisa"]
            if gap == 0:
                self.difference.setText("Exact match. You can approve this bundle.")
                self.difference.setObjectName("good")
                self.approve_all.setEnabled(bundle["pending_paisa"] > 0 or bundle["status"] == "open")
            elif gap > 0:
                self.difference.setText(f"Counted cash is {format_rs(gap)} more than the system.")
                self.difference.setObjectName("bad")
                self.approve_all.setEnabled(False)
            else:
                self.difference.setText(f"Counted cash is {format_rs(abs(gap))} less than the system.")
                self.difference.setObjectName("bad")
                self.approve_all.setEnabled(False)
        self.difference.style().unpolish(self.difference)
        self.difference.style().polish(self.difference)

    def _save_count(self, bundle):
        counted = self._typed_paisa()
        if counted is None:
            warn(self, "Enter the counted cash before approving.")
            return None
        return self.call(
            lambda: self.api.request(
                "POST",
                f"/submissions/{bundle['id']}/count",
                {"amount_rupees": counted // 100},
            )
        )

    def _approve_all(self) -> None:
        bundle = self._current()
        if bundle is None:
            self._explain()
            return
        updated = self._save_count(bundle)
        if updated is None:
            return
        if updated["status"] != "open":
            inform(self, "The counted cash matches. This bundle is closed.")
            self.refresh()
            return
        result = self.call(lambda: self.api.request("POST", f"/submissions/{updated['id']}/approve-all"))
        if result is None:
            return
        inform(self, "Approved. Payment messages are queued for the students in this bundle.")
        self.refresh()

    def _selected_line(self):
        bundle = self._current()
        payment_id = selected_id(self.table)
        if bundle is None or payment_id is None:
            warn(self, "Select a voucher first.")
            return None, None
        line = next((item for item in bundle["lines"] if item["id"] == payment_id), None)
        return bundle, line

    def _approve_one(self) -> None:
        if self._current() is None:
            self._explain()
            return
        bundle, line = self._selected_line()
        if line is None:
            return
        if line["status"] != "submitted":
            warn(self, "That voucher is not waiting for approval.")
            return
        if self._save_count(bundle) is None:
            return
        result = self.call(lambda: self.api.request("POST", f"/payments/{line['id']}/approve"))
        if result is not None:
            self.refresh()

    def _reject_one(self) -> None:
        if self._current() is None:
            self._explain()
            return
        _bundle, line = self._selected_line()
        if line is None:
            return
        if line["status"] != "submitted":
            warn(self, "That voucher is not waiting for approval.")
            return
        reason, ok = QInputDialog.getText(self, "Send back", "Why is this voucher being sent back?")
        if not ok or not reason.strip():
            return
        result = self.call(
            lambda: self.api.request("POST", f"/payments/{line['id']}/reject", {"reason": reason.strip()})
        )
        if result is None:
            return
        if result.get("set_aside_message"):
            inform(self, result["set_aside_message"])
        self.refresh()


def _query(text: str) -> str:
    from urllib.parse import quote

    return quote(text)
