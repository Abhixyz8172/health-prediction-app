"""AI health-risk prediction.

Primary: Google Gemini API (free tier). Fallback: a simple rule-based screen so the app
keeps working when there is no API key, no internet, or the API errors out.
Every remark is saved together with its source so it is always clear which one produced it.
"""
import json
import logging
import os

import requests
from dotenv import load_dotenv

from validators import age_in_years

load_dotenv()
log = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT_SECONDS = 20
MAX_REMARK_LENGTH = 500

PROMPT = """You are a clinical decision-support assistant helping a screening tool.
Patient: {age} years old.
Blood test results:
- Fasting-style glucose: {glucose} mg/dL (normal 70-99, prediabetes 100-125, diabetes range 126+)
- Haemoglobin: {haemoglobin} g/dL (normal about 12-17.5; low suggests anaemia, high suggests polycythaemia)
- Total cholesterol: {cholesterol} mg/dL (desirable below 200, borderline 200-239, high 240+)

Predict the most likely health condition(s) or disease risk suggested by these values.
Reply ONLY with JSON: {{"risk": "Low" | "Moderate" | "High", "remarks": "<max 40 words: possible condition(s) and one next step>"}}.
This is a screening aid, not a diagnosis."""


def rule_based_prediction(glucose, haemoglobin, cholesterol):
    findings, score = [], 0

    if glucose < 70:
        findings.append("low glucose (possible hypoglycaemia)")
        score = max(score, 2)
    elif glucose >= 126:
        findings.append("glucose in diabetic range (possible diabetes)")
        score = max(score, 2)
    elif glucose >= 100:
        findings.append("raised glucose (possible prediabetes)")
        score = max(score, 1)

    if haemoglobin < 12:
        findings.append("low haemoglobin (possible anaemia)")
        score = max(score, 2 if haemoglobin < 10 else 1)
    elif haemoglobin > 17.5:
        findings.append("high haemoglobin (possible polycythaemia or dehydration)")
        score = max(score, 2)

    if cholesterol >= 240:
        findings.append("high cholesterol (cardiovascular risk)")
        score = max(score, 2)
    elif cholesterol >= 200:
        findings.append("borderline cholesterol")
        score = max(score, 1)

    risk = ["Low", "Moderate", "High"][score]
    if not findings:
        return risk, "All values within normal ranges. Maintain a healthy lifestyle and routine check-ups."
    return risk, "; ".join(findings).capitalize() + ". Please consult a doctor for confirmation."


def _gemini_prediction(age, glucose, haemoglobin, cholesterol):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(
            age=age, glucose=glucose, haemoglobin=haemoglobin, cholesterol=cholesterol)}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    resp = requests.post(
        GEMINI_URL.format(model=model),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json=body,
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    data = json.loads(text)
    risk = str(data["risk"]).strip().capitalize()
    if risk not in ("Low", "Moderate", "High"):
        raise ValueError(f"Unexpected risk level: {risk}")
    return risk, str(data["remarks"]).strip()


def predict(dob, glucose, haemoglobin, cholesterol):
    """Return (remarks_text, source). Never raises: falls back to the rule-based screen."""
    age = age_in_years(dob)
    try:
        risk, remarks = _gemini_prediction(age, glucose, haemoglobin, cholesterol)
        source = "Gemini AI"
    except Exception as exc:  # network error, bad key, quota, malformed reply...
        log.warning("Gemini call failed (%s); using rule-based fallback", exc)
        risk, remarks = rule_based_prediction(glucose, haemoglobin, cholesterol)
        source = "Rule-based fallback"
    return f"[{risk} risk] {remarks}"[:MAX_REMARK_LENGTH], source
