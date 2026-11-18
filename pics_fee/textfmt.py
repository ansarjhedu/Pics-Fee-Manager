from __future__ import annotations

from datetime import datetime

_ONES = [
    "Zero",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def format_rs(paisa: int) -> str:
    """Pakistani grouping, whole rupees. 10000000 paisa -> Rs 1,00,000."""
    sign = "-" if paisa < 0 else ""
    rupees = abs(int(paisa)) // 100
    text = str(rupees)
    if len(text) <= 3:
        grouped = text
    else:
        head, tail = text[:-3], text[-3:]
        parts: list[str] = []
        while len(head) > 2:
            parts.append(head[-2:])
            head = head[:-2]
        if head:
            parts.append(head)
        grouped = ",".join(reversed(parts)) + "," + tail
    return f"{sign}Rs {grouped}"


def _under_hundred(n: int) -> str:
    if n < 20:
        return _ONES[n]
    ten, one = divmod(n, 10)
    if one == 0:
        return _TENS[ten]
    return f"{_TENS[ten]} {_ONES[one]}"


def _under_thousand(n: int) -> str:
    hundred, rest = divmod(n, 100)
    parts: list[str] = []
    if hundred:
        parts.append(f"{_ONES[hundred]} Hundred")
    if rest:
        parts.append(_under_hundred(rest))
    return " ".join(parts)


def rupees_in_words(paisa: int) -> str:
    rupees = abs(int(paisa)) // 100
    if rupees == 0:
        return "Rupees Zero Only"
    crore, rupees = divmod(rupees, 10_000_000)
    lakh, rupees = divmod(rupees, 100_000)
    thousand, rest = divmod(rupees, 1000)
    parts: list[str] = []
    if crore:
        parts.append(f"{_under_thousand(crore)} Crore")
    if lakh:
        parts.append(f"{_under_thousand(lakh)} Lakh")
    if thousand:
        parts.append(f"{_under_thousand(thousand)} Thousand")
    if rest:
        parts.append(_under_thousand(rest))
    return "Rupees " + " ".join(parts) + " Only"


def format_date(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return value


def format_when(value: str | None) -> str:
    if not value:
        return "—"
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            stamp = datetime.strptime(value[:19], pattern)
            return stamp.strftime("%d %b %Y, %I:%M %p")
        except ValueError:
            continue
    return value


def parse_rupees(value) -> int:
    """Whole rupees to paisa. Rejects fractions."""
    from pics_fee.errors import DeskError

    if isinstance(value, bool) or value is None:
        raise DeskError("Enter the amount in whole rupees.")
    if isinstance(value, int):
        rupees = value
    elif isinstance(value, float):
        if not value.is_integer():
            raise DeskError("Enter whole rupees, without paisa.")
        rupees = int(value)
    else:
        text = str(value).strip().replace(",", "").replace(" ", "")
        for token in ("Rs.", "Rs", "rs.", "rs", "PKR", "pkr"):
            text = text.replace(token, "")
        text = text.strip()
        if not text.isdigit():
            raise DeskError("Enter whole rupees, without paisa.")
        rupees = int(text)
    if rupees <= 0:
        raise DeskError("Enter an amount greater than zero.")
    if rupees > 100_000_000:
        raise DeskError("That amount is too large.")
    return rupees * 100


def parse_counted(value) -> int:
    """Counted cash may be zero when every note was set aside."""
    from pics_fee.errors import DeskError

    if value is None or (isinstance(value, str) and not str(value).strip()):
        raise DeskError("Enter the counted cash before approving.")
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace(" ", "")
        for token in ("Rs.", "Rs", "rs.", "rs"):
            text = text.replace(token, "")
        text = text.strip()
        if not text.isdigit():
            raise DeskError("Enter the counted cash in whole rupees.")
        rupees = int(text)
    elif isinstance(value, bool):
        raise DeskError("Enter the counted cash in whole rupees.")
    elif isinstance(value, float):
        if not value.is_integer():
            raise DeskError("Enter the counted cash in whole rupees.")
        rupees = int(value)
    else:
        rupees = int(value)
    if rupees < 0:
        raise DeskError("Counted cash cannot be negative.")
    if rupees > 100_000_000:
        raise DeskError("That amount is too large.")
    return rupees * 100
