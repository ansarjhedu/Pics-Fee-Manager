from __future__ import annotations

from html import escape

from pics_fee.textfmt import format_rs, format_when, rupees_in_words


def voucher_html(voucher: dict) -> str:
    status = voucher["status"]
    if status == "approved":
        banner = "Approved by the principal"
        banner_color = "#1d6b3a"
    elif status == "rejected":
        banner = "Sent back by the principal"
        banner_color = "#8f2d2d"
    else:
        banner = "Waiting for principal approval"
        banner_color = "#8a5a12"
    remaining = voucher["remaining_if_approved_paisa"]
    other = voucher.get("other_waiting_paisa") or 0
    other_line = ""
    if other:
        other_line = f"<p>Other vouchers still in the drawer or with the principal: {escape(format_rs(other))}.</p>"
    section = escape(voucher.get("section") or "")
    section_bit = f" ({section})" if section else ""
    return f"""
    <html><body style="font-family: 'Segoe UI', sans-serif; color: #1e1a16;">
      <h1 style="text-align:center; font-size:20px; margin:0;">{escape(voucher['college'])}</h1>
      <p style="text-align:center; margin:4px 0 12px;">Fee voucher</p>
      <p style="text-align:center; background:{banner_color}; color:white; padding:8px; font-weight:600;">
        {escape(banner)}
      </p>
      <p style="font-size:16px;"><b>{escape(voucher['voucher_no'])}</b> &nbsp; {escape(format_when(voucher['created_at']))}</p>
      <table width="100%" cellspacing="0" cellpadding="4">
        <tr><td>Student</td><td><b>{escape(voucher['student_name'])}</b></td></tr>
        <tr><td>Father</td><td>{escape(voucher['father_name'])}</td></tr>
        <tr><td>Admission no.</td><td>{escape(voucher['admission_no'])}</td></tr>
        <tr><td>Class</td><td>{escape(voucher['class_name'])}{section_bit}</td></tr>
        <tr><td>Received by</td><td>{escape(voucher['clerk_name'])}</td></tr>
      </table>
      <p style="font-size:22px; margin:16px 0 4px;"><b>{escape(format_rs(voucher['amount_paisa']))}</b></p>
      <p style="margin-top:0;"><i>{escape(rupees_in_words(voucher['amount_paisa']))}</i></p>
      <table width="100%" cellspacing="0" cellpadding="4">
        <tr><td>Total fee</td><td align="right">{escape(format_rs(voucher['total_paisa']))}</td></tr>
        <tr><td>Paid (approved)</td><td align="right">{escape(format_rs(voucher['paid_paisa']))}</td></tr>
        <tr><td>This voucher</td><td align="right">{escape(format_rs(voucher['amount_paisa']))}</td></tr>
        <tr><td><b>Remaining if this voucher is approved</b></td><td align="right"><b>{escape(format_rs(remaining))}</b></td></tr>
      </table>
      {other_line}
      <p style="margin-top:28px;">Clerk ______________________ &nbsp;&nbsp; Principal ______________________</p>
      <p style="font-size:11px; color:#5c564c;">This voucher is not part of Paid until the principal approves it.</p>
    </body></html>
    """


def handover_html(bundle: dict) -> str:
    rows = []
    for line in bundle["lines"]:
        if line["status"] == "rejected":
            continue
        rows.append(
            "<tr>"
            f"<td>{escape(line['voucher_no'])}</td>"
            f"<td>{escape(line['student_name'])}</td>"
            f"<td>{escape(line['admission_no'])}</td>"
            f"<td>{escape(line['class_name'])}</td>"
            f"<td align='right'>{escape(format_rs(line['amount_paisa']))}</td>"
            "</tr>"
        )
    body = "\n".join(rows) or "<tr><td colspan='5'>No vouchers in this bundle.</td></tr>"
    return f"""
    <html><body style="font-family: 'Segoe UI', sans-serif; color: #1e1a16;">
      <h1 style="text-align:center; font-size:20px; margin:0;">{escape(bundle['college'])}</h1>
      <p style="text-align:center; margin:4px 0 12px;">Cash handover sheet</p>
      <p>Clerk: <b>{escape(bundle['clerk_name'])}</b><br>
         Time: {escape(format_when(bundle['submitted_at']))}<br>
         Students: <b>{bundle['student_count']}</b> &nbsp; Vouchers: <b>{bundle['voucher_count']}</b></p>
      <table width="100%" border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse;">
        <tr style="background:#1d4a3a; color:white;">
          <th align="left">Voucher</th><th align="left">Student</th><th align="left">Admission</th>
          <th align="left">Class</th><th align="right">Amount</th>
        </tr>
        {body}
      </table>
      <p style="font-size:20px;">System total: <b>{escape(format_rs(bundle['expected_paisa']))}</b></p>
      <p>Count the notes before approving this bundle in the fee desk. Approve only when the counted cash matches this total.</p>
      <p style="margin-top:28px;">Clerk ______________________ &nbsp;&nbsp; Principal ______________________</p>
    </body></html>
    """


def print_html(parent, html: str, job_name: str, page: str = "A5") -> bool:
    from PySide6.QtGui import QPageSize, QTextDocument
    from PySide6.QtPrintSupport import QPrintDialog, QPrinter
    from PySide6.QtWidgets import QDialog

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    size = QPageSize.PageSizeId.A5 if page == "A5" else QPageSize.PageSizeId.A4
    printer.setPageSize(QPageSize(size))
    printer.setDocName(job_name)
    dialog = QPrintDialog(printer, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    document = QTextDocument()
    document.setHtml(html)
    document.print_(printer)
    return True


def print_voucher(parent, voucher: dict) -> bool:
    return print_html(parent, voucher_html(voucher), voucher["voucher_no"], "A5")


def print_handover(parent, bundle: dict) -> bool:
    return print_html(parent, handover_html(bundle), f"Handover {bundle['id']}", "A4")
