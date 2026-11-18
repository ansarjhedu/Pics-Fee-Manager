from __future__ import annotations

import re

from pics_fee.errors import DeskError


def normalize_phone(raw: str) -> str:
    """Store Pakistani mobiles as 03XXXXXXXXX."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("92") and len(digits) == 12:
        local = "0" + digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        local = digits
    elif len(digits) == 10 and digits.startswith("3"):
        local = "0" + digits
    else:
        raise DeskError("Enter a Pakistani mobile number, for example 03001234567.")
    if not re.fullmatch(r"03\d{9}", local):
        raise DeskError("Enter a Pakistani mobile number, for example 03001234567.")
    return local


def to_sms_phone(local: str) -> str:
    """03XXXXXXXXX -> 923XXXXXXXXX."""
    local = normalize_phone(local)
    return "92" + local[1:]
