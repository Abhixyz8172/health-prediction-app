"""Input validation for patient records.

Every validator returns a (clean_value, error_message) pair. If the input is fine,
error_message is None. If not, clean_value is None and error_message explains why.
"""
import re
from datetime import date, datetime

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,99}$")
NUMBER_RE = re.compile(r"^\d+(\.\d+)?$")
DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")

# (min, max, unit) - wide physiological limits, only to catch typos / impossible values
LAB_LIMITS = {
    "glucose": (20, 800, "mg/dL"),
    "haemoglobin": (3, 25, "g/dL"),
    "cholesterol": (50, 800, "mg/dL"),
}

MIN_YEAR = 1900


def validate_name(value):
    value = (value or "").strip()
    if not value:
        return None, "Full name is required."
    if not NAME_RE.match(value):
        return None, "Name may contain only letters, spaces, apostrophes, dots and hyphens (2-100 characters)."
    return " ".join(value.split()), None


def validate_email(value):
    value = (value or "").strip()
    if not value:
        return None, "Email is required."
    if not EMAIL_RE.match(value):
        return None, f"'{value}' is not a valid email address (expected something like name@example.com)."
    return value.lower(), None


def validate_dob(value, today=None):
    """Accepts dd/mm/yyyy. Dots or dashes as separators are converted to slashes."""
    today = today or date.today()
    value = (value or "").strip()
    if not value:
        return None, "Date of birth is required."
    value = value.replace(".", "/").replace("-", "/")
    m = DATE_RE.match(value)
    if not m:
        return None, "Date of birth must be in dd/mm/yyyy format."
    day, month, year = (int(g) for g in m.groups())
    try:
        dob = datetime(year, month, day).date()
    except ValueError:
        return None, f"{day:02d}/{month:02d}/{year} is not a real calendar date."
    if dob > today:
        return None, "Date of birth cannot be in the future."
    if year < MIN_YEAR:
        return None, f"Date of birth cannot be before {MIN_YEAR}."
    return dob, None


def validate_lab(field, value):
    value = str(value if value is not None else "").strip()
    label = field.capitalize()
    low, high, unit = LAB_LIMITS[field]
    if not value:
        return None, f"{label} is required."
    if not NUMBER_RE.match(value):
        return None, f"{label} must be a number (got '{value}')."
    number = float(value)
    if not (low <= number <= high):
        return None, f"{label} must be between {low} and {high} {unit}."
    return number, None


def validate_patient(data, today=None):
    """Validate a whole record. Returns (clean_dict, errors_dict)."""
    clean, errors = {}, {}
    checks = {
        "full_name": lambda: validate_name(data.get("full_name")),
        "dob": lambda: validate_dob(data.get("dob"), today),
        "email": lambda: validate_email(data.get("email")),
        "glucose": lambda: validate_lab("glucose", data.get("glucose")),
        "haemoglobin": lambda: validate_lab("haemoglobin", data.get("haemoglobin")),
        "cholesterol": lambda: validate_lab("cholesterol", data.get("cholesterol")),
    }
    for field, check in checks.items():
        value, error = check()
        if error:
            errors[field] = error
        else:
            clean[field] = value
    return clean, errors


def age_in_years(dob, today=None):
    today = today or date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
