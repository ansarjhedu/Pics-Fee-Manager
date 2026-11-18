from __future__ import annotations

import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication, QMessageBox

    from pics_fee.ui.theme import apply_theme
    from pics_fee.ui.window import MainWindow

    app = QApplication(sys.argv)
    apply_theme(app)
    try:
        from pics_fee.machine import ensure_machine_role

        ensure_machine_role("clerk")
        window = MainWindow(mode="clerk")
        window.show()
        return app.exec()
    except Exception as exc:
        QMessageBox.critical(None, "PICS Fee", f"The fee desk could not open.\n\n{exc}")
        return 1
