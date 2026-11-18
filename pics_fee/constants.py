COLLEGE_NAME = "Punjab Inter College of Sciences"
APP_NAME = "PICS Fee Desk"
PORT = 8765
SESSION_HOURS = 12
PASSWORD_ITERATIONS = 200_000
MIN_PASSWORD = 8
LOCK_AFTER = 5
LOCK_MINUTES = 5
VOUCHER_PREFIX = "PICS"

PAYMENT_TEMPLATE = (
    "{college}: Fee {amount} received for {student} ({class_name}), "
    "admission {admission_no}. Voucher {voucher}. Total {total}. Paid {paid}. "
    "Remaining {remaining}. Last date: {due_date}."
)

REMINDER_TEMPLATE = (
    "{college}: Reminder for {student} ({class_name}), admission {admission_no}. "
    "Remaining fee {remaining}. Please pay before {due_date}."
)

TEMPLATE_FIELDS = (
    "college",
    "student",
    "father",
    "class_name",
    "section",
    "admission_no",
    "amount",
    "voucher",
    "total",
    "paid",
    "remaining",
    "due_date",
    "date",
)
