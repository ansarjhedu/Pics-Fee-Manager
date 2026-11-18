from __future__ import annotations

import sys
import traceback


def main() -> int:
    from PySide6.QtWidgets import QApplication, QMessageBox

    from pics_fee.certs import lan_ips
    from pics_fee.constants import PORT
    from pics_fee.runtime import ServerStartError, ensure_server_running
    from pics_fee.ui.theme import apply_theme
    from pics_fee.ui.window import MainWindow

    app = QApplication(sys.argv)
    apply_theme(app)
    try:
        from pics_fee.runtime import ensure_stdio

        ensure_stdio()
        from pics_fee.machine import ensure_machine_role

        ensure_machine_role("principal")
        fingerprint = ensure_server_running()
        window = MainWindow(mode="principal", host="127.0.0.1", port=PORT, fingerprint=fingerprint, lan_ips=lan_ips())
        window.show()
        return app.exec()
    except ServerStartError as exc:
        QMessageBox.critical(None, "PICS Fee", str(exc))
        return 1
    except Exception as exc:
        from pics_fee.paths import data_dir

        try:
            (data_dir() / "startup.log").write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        QMessageBox.critical(None, "PICS Fee", f"The fee desk could not open.\n\n{exc}")
        return 1
