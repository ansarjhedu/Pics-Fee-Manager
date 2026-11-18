from __future__ import annotations

import contextvars

machine_var: contextvars.ContextVar[str] = contextvars.ContextVar("pics_machine", default="")


def current_machine() -> str:
    return machine_var.get()
