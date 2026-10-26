"""Runs the 10 rows from the assignment table, exactly as given, through the service layer.

Run:  pytest -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ai_service  # noqa: E402
import database as db  # noqa: E402
import services  # noqa: E402

# (test #, name, dob, email, glucose, haemoglobin, cholesterol, expected field errors)
CASES = [
    (1, "Robyn Pears", "28.01.1960", "robyn@gmail.com", "232", "13.5", "180", set()),
    (2, "John Hunter", "10.12.1990", "hunter@gmail", "94", "15", "200", {"email"}),
    (3, "Darryl Tim", "12.11.1993", "timd@smh.com.au", "240", "18.6", "326", set()),
    (4, "Peter Larry", "31.11.2001", "Larry@hotmail.com", "88", "11.5", "165", {"dob"}),
    (5, "Sam Kerr", "09.12.2006", "sam@news.com.au", "198", "8.9", "192", set()),
    (6, "Robyn Pears", "28.01.1960", "robyn@gmail.com", "232", "13.5", "180", {"email"}),
    (7, "Madison XI", "12.09.1998", "madison@hotmail.com", "85", "7.6", "163", set()),
    (8, "Kris Wu", "19.10.2030", "Kris.wu.gmail.com", "79", "16.5", "197", {"dob", "email"}),
    (9, "Tenille Singh", "30.11.1991", "Tenille@yahoo.com", "101", "15", "310", set()),
    (10, "Prem Kumar", "28.04.1990", "prem@telstra.com", "155", "12.5", "265", set()),
]


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)  # force the offline fallback
    db.init_db()


def row(case):
    _, name, dob, email, glu, hb, chol, _ = case
    return {"full_name": name, "dob": dob, "email": email,
            "glucose": glu, "haemoglobin": hb, "cholesterol": chol}


def add_all():
    return {c[0]: services.add_patient(row(c)) for c in CASES}


@pytest.mark.parametrize("case", CASES, ids=[f"test{c[0]}" for c in CASES])
def test_each_case(case):
    results = add_all()
    result = results[case[0]]
    expected = case[7]
    assert set(result.errors) == expected
    assert result.ok == (not expected)


def test_seven_valid_records_saved():
    add_all()
    names = [p["full_name"] for p in services.list_patients()]
    assert names == ["Robyn Pears", "Darryl Tim", "Sam Kerr", "Madison XI", "Tenille Singh", "Prem Kumar"]


def test_edit_email_and_delete():
    add_all()
    prem = next(p for p in services.list_patients() if p["full_name"] == "Prem Kumar")
    data = row(CASES[9])
    data["email"] = "gokul@infocare.com"
    assert services.update_patient(prem["id"], data).ok
    assert services.get_patient(prem["id"])["email"] == "gokul@infocare.com"

    before = len(services.list_patients())
    assert services.delete_patient(prem["id"])
    assert len(services.list_patients()) == before - 1


def test_edit_cannot_steal_another_records_email():
    add_all()
    darryl = next(p for p in services.list_patients() if p["full_name"] == "Darryl Tim")
    data = row(CASES[2])
    data["email"] = "robyn@gmail.com"
    result = services.update_patient(darryl["id"], data)
    assert not result.ok and "email" in result.errors


@pytest.mark.parametrize("value", ["abc", "", "-5", "1e3", "nan", "12,5"])
def test_non_numeric_lab_values_rejected(value):
    data = row(CASES[0])
    data["glucose"] = value
    result = services.add_patient(data)
    assert not result.ok and "glucose" in result.errors


def test_rule_based_remarks():
    assert "High" == ai_service.rule_based_prediction(240, 18.6, 326)[0]
    assert "Low" == ai_service.rule_based_prediction(90, 14, 180)[0]
    assert "anaemia" in ai_service.rule_based_prediction(85, 7.6, 163)[1]
