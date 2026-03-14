from fastapi.testclient import TestClient

from app.domain.personal_loan.qualification_rules import normalize_currency_inr
from app.main import app

client = TestClient(app)


def test_get_personal_loan_spec():
    response = client.get("/api/v1/personal-loan/spec")
    assert response.status_code == 200

    data = response.json()
    assert data["product"] == "personal_loan"
    assert len(data["intents"]) > 0
    assert len(data["slots"]) > 0
    assert "sections" in data["script"]


def test_currency_normalization():
    assert normalize_currency_inr("35k") == 35000
    assert normalize_currency_inr("2 lakh") == 200000
    assert normalize_currency_inr("4.5 lacs") == 450000


def test_qualify_success():
    payload = {
        "slots": {
            "language": "English",
            "consent": "yes",
            "interest": "yes",
            "employment_type": "salaried",
            "monthly_income": "45000",
            "loan_amount": "3 lakh",
            "city": "ghaziabad"
        }
    }

    response = client.post("/api/v1/personal-loan/qualify", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "qualified"
    assert data["normalized_slots"]["city"] == "Ghaziabad"


def test_qualify_low_income():
    payload = {
        "slots": {
            "language": "Hindi",
            "consent": "haan",
            "interest": "yes",
            "employment_type": "self employed",
            "monthly_income": "25000",
            "loan_amount": "2 lakh",
            "city": "noida"
        }
    }

    response = client.post("/api/v1/personal-loan/qualify", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "not_qualified"


def test_qualify_human_escalation():
    payload = {
        "slots": {
            "human_assistance_requested": "yes"
        }
    }

    response = client.post("/api/v1/personal-loan/qualify", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "escalate_to_human"
    assert data["next_step"] == "human_callback"