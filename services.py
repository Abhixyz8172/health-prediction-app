"""Business logic: validate -> check duplicates -> call AI -> save.

The UI only calls these functions, so the same rules apply no matter what front end is used.
"""
import sqlite3
from dataclasses import dataclass, field

import ai_service
import database as db
from validators import validate_patient

LAB_FIELDS = ("glucose", "haemoglobin", "cholesterol")


@dataclass
class Result:
    ok: bool
    errors: dict = field(default_factory=dict)
    patient_id: int | None = None


def _check_duplicate_email(clean, exclude_id=None):
    if db.email_exists(clean["email"], exclude_id):
        return {"email": f"A patient with email '{clean['email']}' already exists (duplicate record)."}
    return {}


def add_patient(data):
    clean, errors = validate_patient(data)
    if not errors:
        errors = _check_duplicate_email(clean)
    if errors:
        return Result(False, errors)

    clean["remarks"], clean["remarks_source"] = ai_service.predict(
        clean["dob"], clean["glucose"], clean["haemoglobin"], clean["cholesterol"])
    try:
        patient_id = db.insert_patient(clean)
    except sqlite3.IntegrityError:  # safety net if two inserts race past the check above
        return Result(False, {"email": "A patient with this email already exists (duplicate record)."})
    return Result(True, patient_id=patient_id)


def update_patient(patient_id, data):
    existing = db.get_patient(patient_id)
    if existing is None:
        return Result(False, {"id": "Record not found - it may have been deleted."})

    clean, errors = validate_patient(data)
    if not errors:
        errors = _check_duplicate_email(clean, exclude_id=patient_id)
    if errors:
        return Result(False, errors)

    # Only re-run the AI when something it depends on has changed.
    inputs_changed = clean["dob"] != existing["dob"] or any(clean[f] != existing[f] for f in LAB_FIELDS)
    if inputs_changed:
        clean["remarks"], clean["remarks_source"] = ai_service.predict(
            clean["dob"], clean["glucose"], clean["haemoglobin"], clean["cholesterol"])
    else:
        clean["remarks"], clean["remarks_source"] = existing["remarks"], existing["remarks_source"]

    db.update_patient(patient_id, clean)
    return Result(True, patient_id=patient_id)


def delete_patient(patient_id):
    return db.delete_patient(patient_id)


def list_patients():
    return db.list_patients()


def get_patient(patient_id):
    return db.get_patient(patient_id)
