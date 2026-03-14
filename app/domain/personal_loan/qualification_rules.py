import re
from typing import Any


YES_WORDS = {
    "yes", "y", "haan", "ha", "sure", "okay", "ok", "go ahead", "continue"
}
NO_WORDS = {
    "no", "n", "nahin", "nahi", "not now", "don't", "do not", "nope"
}

SALARIED_WORDS = {
    "salaried", "salary", "job", "working", "employee", "service"
}
SELF_EMPLOYED_WORDS = {
    "self employed", "self-employed", "business", "businessman", "owner", "freelancer"
}

LOAN_PURPOSE_MAP = {
    "wedding": "wedding",
    "marriage": "wedding",
    "medical": "medical",
    "hospital": "medical",
    "travel": "travel",
    "trip": "travel",
    "education": "education",
    "study": "education",
    "renovation": "home_renovation",
    "home renovation": "home_renovation",
    "repair": "home_renovation",
    "debt": "debt_consolidation",
    "credit card": "debt_consolidation",
    "consolidation": "debt_consolidation",
}


def normalize_yes_no(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value

    if value is None:
        return None

    text = str(value).strip().lower()
    if text in YES_WORDS:
        return True
    if text in NO_WORDS:
        return False
    return None


def normalize_language(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip().lower()

    if not text:
        return None

    if re.search(r"[\u0900-\u097F]", text):
        return "hi-IN"

    hindi_markers = {"hindi", "hinglish", "hi", "hindustani"}
    if text in hindi_markers:
        return "hi-IN"

    return "en"


def normalize_employment_type(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip().lower()

    if not text:
        return None

    if text in SALARIED_WORDS or any(word in text for word in SALARIED_WORDS):
        return "salaried"

    if text in SELF_EMPLOYED_WORDS or any(word in text for word in SELF_EMPLOYED_WORDS):
        return "self_employed"

    return None


def normalize_city(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    return text.title()


def normalize_currency_inr(value: Any) -> int | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip().lower()
    if not text:
        return None

    text = text.replace(",", "").replace("₹", "").replace("rs.", "").replace("rs", "").strip()

    plain_number = re.fullmatch(r"\d+(\.\d+)?", text)
    if plain_number:
        return int(float(text))

    match = re.search(r"(\d+(\.\d+)?)", text)
    if not match:
        return None

    number = float(match.group(1))

    if any(token in text for token in ["lakh", "lakhs", "lac", "lacs"]):
        return int(number * 100000)

    if any(token in text for token in ["crore", "crores", "cr"]):
        return int(number * 10000000)

    if text.endswith("k") or " thousand" in text:
        return int(number * 1000)

    return int(number)


def normalize_age(value: Any) -> int | None:
    if value is None:
        return None

    if isinstance(value, int):
        return value if 18 <= value <= 75 else None

    text = str(value).strip().lower()
    match = re.search(r"\b(\d{2})\b", text)
    if not match:
        return None

    age = int(match.group(1))
    if 18 <= age <= 75:
        return age
    return None


def normalize_duration_months(value: Any) -> int | None:
    if value is None:
        return None

    if isinstance(value, int):
        return value if value >= 0 else None

    text = str(value).strip().lower()
    match = re.search(r"(\d+(\.\d+)?)", text)
    if not match:
        return None

    number = float(match.group(1))
    if "year" in text:
        return int(number * 12)
    if "month" in text:
        return int(number)
    return None


def normalize_loan_purpose(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip().lower()
    if not text:
        return None

    for key, normalized in LOAN_PURPOSE_MAP.items():
        if key in text:
            return normalized

    return "other"


def normalize_slots(raw_slots: dict[str, Any]) -> dict[str, Any]:
    return {
        "language": normalize_language(raw_slots.get("language")),
        "consent": normalize_yes_no(raw_slots.get("consent")),
        "interest": normalize_yes_no(raw_slots.get("interest")),
        "city": normalize_city(raw_slots.get("city")),
        "employment_type": normalize_employment_type(raw_slots.get("employment_type")),
        "monthly_income": normalize_currency_inr(raw_slots.get("monthly_income")),
        "loan_amount": normalize_currency_inr(raw_slots.get("loan_amount")),
        "age": normalize_age(raw_slots.get("age")),
        "work_experience_months": normalize_duration_months(raw_slots.get("work_experience_months")),
        "business_vintage_months": normalize_duration_months(raw_slots.get("business_vintage_months")),
        "existing_monthly_emi": normalize_currency_inr(raw_slots.get("existing_monthly_emi")),
        "loan_purpose": normalize_loan_purpose(raw_slots.get("loan_purpose")) if raw_slots.get("loan_purpose") else None,
        "callback_time": str(raw_slots.get("callback_time")).strip() if raw_slots.get("callback_time") else None,
        "human_assistance_requested": normalize_yes_no(raw_slots.get("human_assistance_requested")),
    }


def evaluate_personal_loan(raw_slots: dict[str, Any]) -> tuple[dict[str, Any], str, list[str], str]:
    normalized = normalize_slots(raw_slots)
    reasons: list[str] = []

    if normalized["human_assistance_requested"] is True:
        return normalized, "escalate_to_human", ["Customer explicitly requested a human agent"], "human_callback"

    if normalized["consent"] is False:
        return normalized, "do_not_contact", ["Customer did not consent to continue"], "end_call"

    if normalized["consent"] is None:
        return normalized, "incomplete", ["Consent is missing or unclear"], "ask_for_consent"

    if normalized["interest"] is False:
        return normalized, "not_interested", ["Customer is not interested in a personal loan"], "close_politely"

    if normalized["interest"] is None:
        reasons.append("Interest in personal loan is missing or unclear")

    required_slots = [
        "language",
        "interest",
        "city",
        "employment_type",
        "monthly_income",
        "loan_amount",
    ]
    missing = [slot for slot in required_slots if normalized.get(slot) in (None, "")]

    if missing:
        reasons.append(f"Missing required slots: {', '.join(missing)}")
        return normalized, "incomplete", reasons, "clarify_missing_details"

    income_threshold = 25000 if normalized["employment_type"] == "salaried" else 40000

    if normalized["monthly_income"] < income_threshold:
        return (
            normalized,
            "not_qualified",
            [f"Monthly income is below the base threshold for {normalized['employment_type']} applicants"],
            "close_politely",
        )

    if not (50000 <= normalized["loan_amount"] <= 4000000):
        return (
            normalized,
            "not_qualified",
            ["Requested loan amount is outside the supported range of 50,000 to 40,00,000 INR"],
            "close_politely",
        )

    age = normalized.get("age")
    if age is not None:
        max_age = 58 if normalized["employment_type"] == "salaried" else 65
        if age < 21 or age > max_age:
            return (
                normalized,
                "not_qualified",
                [f"Age is outside the base screening range for {normalized['employment_type']} applicants"],
                "close_politely",
            )

    if normalized["employment_type"] == "salaried":
        work_experience_months = normalized.get("work_experience_months")
        if work_experience_months is not None and work_experience_months < 6:
            return (
                normalized,
                "manual_review",
                ["Work experience appears short for instant screening and needs specialist review"],
                "arrange_human_callback",
            )
    else:
        business_vintage_months = normalized.get("business_vintage_months")
        if business_vintage_months is not None and business_vintage_months < 12:
            return (
                normalized,
                "manual_review",
                ["Business vintage appears short and needs specialist review"],
                "arrange_human_callback",
            )

    existing_monthly_emi = normalized.get("existing_monthly_emi")
    if existing_monthly_emi is not None and existing_monthly_emi > normalized["monthly_income"] * 0.6:
        return (
            normalized,
            "manual_review",
            ["Existing EMI burden appears high and needs specialist review"],
            "arrange_human_callback",
        )

    return (
        normalized,
        "qualified",
        ["Customer meets the base rule criteria for personal loan follow-up"],
        "arrange_human_callback",
    )