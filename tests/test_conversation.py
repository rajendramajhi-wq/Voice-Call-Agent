from fastapi.testclient import TestClient

from app.core.masking import mask_sensitive_text
from app.main import app

client = TestClient(app)


def start_session():
    response = client.post("/api/v1/conversation/start")
    assert response.status_code == 200
    return response.json()


def test_start_conversation():
    data = start_session()
    assert data["state"] == "awaiting_consent"
    assert data["qualification_status"] == "in_progress"
    assert data["call_status"] == "initiated"
    assert "personal loan enquiry" in data["assistant_text"].lower()


def test_hindi_switch():
    started = start_session()
    session_id = started["session_id"]

    response = client.post(
        "/api/v1/conversation/turn",
        json={"session_id": session_id, "user_text": "haan hindi mein baat kariye"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["detected_language"] == "hi-IN"
    assert data["state"] == "awaiting_interest"


def test_busy_callback_flow():
    started = start_session()
    session_id = started["session_id"]

    response_1 = client.post(
        "/api/v1/conversation/turn",
        json={"session_id": session_id, "user_text": "call me later I am busy"},
    )
    assert response_1.status_code == 200
    assert response_1.json()["state"] == "awaiting_callback_time"
    assert response_1.json()["call_status"] == "busy"

    response_2 = client.post(
        "/api/v1/conversation/turn",
        json={"session_id": session_id, "user_text": "tomorrow after 6 pm"},
    )
    assert response_2.status_code == 200
    assert response_2.json()["state"] == "completed"
    assert response_2.json()["call_status"] == "callback_scheduled"


def test_successful_qualification_conversation():
    started = start_session()
    session_id = started["session_id"]

    steps = [
        "yes",
        "yes I am interested in a personal loan",
        "I am salaried",
        "45000",
        "3 lakh",
        "Ghaziabad",
    ]

    last_response = None
    for step in steps:
        last_response = client.post(
            "/api/v1/conversation/turn",
            json={"session_id": session_id, "user_text": step},
        )

    assert last_response is not None
    assert last_response.status_code == 200

    data = last_response.json()
    assert data["state"] == "completed"
    assert data["qualification_status"] == "qualified"
    assert data["normalized_slots"]["monthly_income"] == 45000
    assert data["normalized_slots"]["loan_amount"] == 300000
    assert data["normalized_slots"]["city"] == "Ghaziabad"


def test_ambiguous_retries_escalate_to_human():
    started = start_session()
    session_id = started["session_id"]

    for _ in range(3):
        response = client.post(
            "/api/v1/conversation/turn",
            json={"session_id": session_id, "user_text": "maybe"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "completed"
    assert data["qualification_status"] == "escalated_to_human"
    assert data["call_status"] == "escalated"


def test_sensitive_masking():
    text = "my otp is 123456 and aadhaar number is 1234 5678 9123"
    masked = mask_sensitive_text(text)

    assert "123456" not in masked
    assert "1234 5678 9123" not in masked
    assert "otp is ****" in masked.lower()
    assert "XXXX XXXX 9123" in masked