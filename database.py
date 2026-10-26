"""SQLite persistence layer. Only this module talks to the database."""
import os
import sqlite3
from contextlib import contextmanager
from datetime import date

DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patients.db")


def db_path():
    return os.getenv("DB_PATH", DEFAULT_DB)


@contextmanager
def connect():
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS patients (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name      TEXT NOT NULL,
                dob            TEXT NOT NULL,                  -- stored as ISO yyyy-mm-dd
                email          TEXT NOT NULL UNIQUE COLLATE NOCASE,
                glucose        REAL NOT NULL,
                haemoglobin    REAL NOT NULL,
                cholesterol    REAL NOT NULL,
                remarks        TEXT NOT NULL DEFAULT '',
                remarks_source TEXT NOT NULL DEFAULT ''
            )
            """
        )


def _row_to_dict(row):
    d = dict(row)
    d["dob"] = date.fromisoformat(d["dob"])
    return d


def email_exists(email, exclude_id=None):
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM patients WHERE email = ? AND id IS NOT ?", (email, exclude_id)
        ).fetchone()
    return row is not None


def insert_patient(p):
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO patients
               (full_name, dob, email, glucose, haemoglobin, cholesterol, remarks, remarks_source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (p["full_name"], p["dob"].isoformat(), p["email"], p["glucose"],
             p["haemoglobin"], p["cholesterol"], p["remarks"], p["remarks_source"]),
        )
        return cur.lastrowid


def get_patient(patient_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_patients():
    with connect() as conn:
        rows = conn.execute("SELECT * FROM patients ORDER BY id").fetchall()
    return [_row_to_dict(r) for r in rows]


def update_patient(patient_id, p):
    with connect() as conn:
        conn.execute(
            """UPDATE patients SET full_name=?, dob=?, email=?, glucose=?, haemoglobin=?,
               cholesterol=?, remarks=?, remarks_source=? WHERE id=?""",
            (p["full_name"], p["dob"].isoformat(), p["email"], p["glucose"],
             p["haemoglobin"], p["cholesterol"], p["remarks"], p["remarks_source"], patient_id),
        )


def delete_patient(patient_id):
    with connect() as conn:
        cur = conn.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
        return cur.rowcount > 0
