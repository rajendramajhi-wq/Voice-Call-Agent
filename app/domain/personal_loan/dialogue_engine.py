import re
import time
from datetime import datetime, timezone
from app.domain.personal_loan.qualification_rules import (
    evaluate_personal_loan,
    normalize_city,
    normalize_currency_inr,
    normalize_duration_months,
    normalize_employment_type,
    normalize_loan_purpose,
    normalize_yes_no,
)
# from flask import session

from fastapi import HTTPException

from app.core.masking import contains_sensitive_financial_input, mask_sensitive_text
from app.core.session_store import create_session, get_session, list_sessions, save_session
from app.domain.models import (
    CallSession,
    ConversationTurnRequest,
    ConversationTurnResponse,
    SessionDetailResponse,
    StartConversationResponse,
    TranscriptTurn,
)
from app.domain.personal_loan.qualification_rules import (
    evaluate_personal_loan,
    normalize_city,
    normalize_currency_inr,
    normalize_employment_type,
    normalize_yes_no,
)


PROMPTS = {
    "opening": {
        "en": "Hello, this is Rajendra calling regarding your personal loan enquiry. This is a quick eligibility check and next-step call that takes under a minute. I can continue in English or Hindi. Is this a good time?",
        "hi-IN": "Hello, main Rajendra bol raha hoon aapki personal loan enquiry ke regarding. Yeh ek quick eligibility aur next-step call hai jo ek minute se kam leta hai. Main English ya Hindi mein continue kar sakta hoon. Kya abhi baat karna convenient hai?",
    },
    "ask_consent": {
        "en": "With your permission, I will ask a few quick questions to understand your basic eligibility. Shall I continue?",
        "hi-IN": "Aapki permission se main basic eligibility samajhne ke liye kuch quick questions poochunga. Kya main continue karoon?",
    },
    "ask_interest": {
        "en": "Just to confirm, are you currently looking for a personal loan?",
        "hi-IN": "Confirm karne ke liye pooch raha hoon, kya aap abhi personal loan dekh rahe hain?",
    },
    "ask_employment_type": {
        "en": "Are you salaried or self-employed?",
        "hi-IN": "Aap salaried hain ya self-employed?",
    },
    "ask_monthly_income": {
        "en": "What is your approximate monthly income?",
        "hi-IN": "Aapki approximate monthly income kitni hai?",
    },
    "ask_loan_amount": {
        "en": "Roughly how much loan amount are you looking for?",
        "hi-IN": "Lagbhag kitne amount ka loan chahiye?",
    },
    "ask_city": {
        "en": "Which city are you based in?",
        "hi-IN": "Aap kis city mein based hain?",
    },
    "busy_callback": {
        "en": "No problem. I can arrange a callback. What time would be best for you?",
        "hi-IN": "Koi baat nahi. Main callback arrange kar deta hoon. Aapke liye kaunsa time best rahega?",
    },
    "human_handoff": {
        "en": "Understood. I will arrange a callback from a loan specialist.",
        "hi-IN": "Samajh gaya. Main loan specialist ka callback arrange kar deta hoon.",
    },
    "qualified": {
        "en": "Thank you. Based on these basic details, I can arrange the next step with a loan specialist.",
        "hi-IN": "Dhanyavaad. In basic details ke basis par main next step ke liye loan specialist ka callback arrange kar sakta hoon.",
    },
    "not_qualified": {
        "en": "Thank you. Based on the current details, this does not fit the base screening right now.",
        "hi-IN": "Dhanyavaad. Current details ke hisaab se yeh abhi base screening mein fit nahi baithta.",
    },
    "not_interested": {
        "en": "Understood. I will mark this enquiry as not interested and we will not proceed further.",
        "hi-IN": "Samajh gaya. Main is enquiry ko not interested mark kar deta hoon aur aage proceed nahi karenge.",
    },
    "sensitive_redirect": {
        "en": "For your safety, please do not share OTP, CVV, full Aadhaar, or full card details on this call. I only need basic eligibility details.",
        "hi-IN": "Aapki safety ke liye kripya OTP, CVV, poora Aadhaar, ya poore card details is call par share na karein. Mujhe sirf basic eligibility details chahiye.",
    },
    "fallback_escalate": {
        "en": "I am not getting a clear response. I will arrange a callback from a human loan specialist.",
        "hi-IN": "Mujhe clear response nahi mil raha hai. Main human loan specialist ka callback arrange kar deta hoon.",
    },
}


BUSY_MARKERS = {
    "busy",
    "call me later",
    "later",
    "not now",
    "baad mein",
    "baad me",
    "later please",
    "callback later",
}
HUMAN_MARKERS = {
    "human",
    "person",
    "representative",
    "executive",
    "agent",
    "kisi se baat",
    "insaan",
}
INTEREST_NO_MARKERS = {
    "not interested",
    "no need",
    "don't need",
    "do not need",
    "mujhe nahi chahiye",
    "interest nahi hai",
}
INTEREST_YES_MARKERS = {
    "interested",
    "need a personal loan",
    "need personal loan",
    "looking for a personal loan",
    "want a personal loan",
    "loan chahiye",
    "personal loan chahiye",
}
HINDI_MARKERS = {
    "hindi",
    "hinglish",
    "hindi mein",
    "hindi me",
}
CITY_STOPWORDS = {
    "yes",
    "no",
    "hindi",
    "english",
    "salaried",
    "self employed",
    "self-employed",
    "personal loan",
    "loan",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _prompt(key: str, language: str) -> str:
    lang = "hi-IN" if language == "hi-IN" else "en"
    return PROMPTS[key][lang]


def _append_turn(session: CallSession, speaker: str, text: str) -> None:
    session.transcript.append(
        TranscriptTurn(
            speaker=speaker,
            masked_text=mask_sensitive_text(text),
            timestamp=_now_iso(),
        )
    )


def _detect_language(text: str, current_language: str) -> str:
    lowered = text.strip().lower()

    if re.search(r"[\u0900-\u097F]", lowered):
        return "hi-IN"

    if any(marker in lowered for marker in HINDI_MARKERS):
        return "hi-IN"

    return current_language


def _contains_any(text: str, phrases: set[str]) -> bool:
    for phrase in phrases:
        pattern = rf"(?<!\w){re.escape(phrase)}(?!\w)"
        if re.search(pattern, text):
            return True
    return False

def _extract_yes_no_phrase(text: str) -> bool | None:
    yes_patterns = [
        r"\byes\b",
        r"\bhaan\b",
        r"\bha\b",
        r"\bsure\b",
        r"\bok\b",
        r"\bokay\b",
        r"\bgo ahead\b",
        r"\bcontinue\b",
    ]
    no_patterns = [
        r"\bno\b",
        r"\bnahin\b",
        r"\bnahi\b",
        r"\bnope\b",
        r"\bnot now\b",
        r"\bdon't\b",
        r"\bdo not\b",
    ]

    for pattern in yes_patterns:
        if re.search(pattern, text):
            return True

    for pattern in no_patterns:
        if re.search(pattern, text):
            return False

    return None

def _extract_interest(text: str) -> bool | None:
    if _contains_any(text, INTEREST_NO_MARKERS):
        return False
    if _contains_any(text, INTEREST_YES_MARKERS):
        return True
    return None

def _extract_age(text: str) -> int | None:
    patterns = [
        r"\bage\s*(?:is|:)?\s*(\d{2})\b",
        r"\bi am\s*(\d{2})\s*years?\s*old\b",
        r"\bmeri age\s*(\d{2})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            age = int(match.group(1))
            if 18 <= age <= 75:
                return age
    return None


def _extract_duration_months(text: str, keyword_group: str) -> int | None:
    if keyword_group == "work":
        trigger_words = ["experience", "working", "job", "service"]
    else:
        trigger_words = ["business", "shop", "firm", "self employed", "self-employed"]

    if not any(word in text.lower() for word in trigger_words):
        return None

    patterns = [
        r"(\d+(\.\d+)?)\s*years?",
        r"(\d+(\.\d+)?)\s*months?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return normalize_duration_months(match.group(0))
    return None


def _extract_existing_emi(text: str) -> int | None:
    if "emi" not in text.lower():
        return None
    return normalize_currency_inr(text)


def _extract_loan_purpose(text: str) -> str | None:
    purpose = normalize_loan_purpose(text)
    return purpose if purpose != "other" else None

def _extract_city(text: str, state: str) -> str | None:
    patterns = [
        r"(?:live in|reside in|located in|from|city is|based in)\s+([A-Za-z ]{2,40})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            city = normalize_city(match.group(1).strip(" .,!?:;"))
            if city and city.lower() not in CITY_STOPWORDS:
                return city

    segments = [seg.strip(" .,!?:;") for seg in re.split(r"[,/\n]", text) if seg.strip()]
    for segment in reversed(segments):
        if re.fullmatch(r"[A-Za-z ]{2,40}", segment):
            city = normalize_city(segment)
            if city and city.lower() not in CITY_STOPWORDS:
                if state == "awaiting_city" or len(segments) > 1:
                    return city

    if state == "awaiting_city":
        candidate = text.strip(" .,!?:;")
        if re.fullmatch(r"[A-Za-z ]{2,40}", candidate):
            city = normalize_city(candidate)
            if city and city.lower() not in CITY_STOPWORDS:
                return city

    return None

def _extract_slots(text: str, state: str) -> tuple[dict[str, object], dict[str, float], dict[str, bool]]:
    lowered = text.strip().lower()

    slots: dict[str, object] = {}
    confidence: dict[str, float] = {}
    flags = {
        "busy": _contains_any(lowered, BUSY_MARKERS),
        "human": _contains_any(lowered, HUMAN_MARKERS),
    }

    yes_no = _extract_yes_no_phrase(lowered)
    if yes_no is not None and state == "awaiting_consent":
        slots["consent"] = yes_no
        confidence["consent"] = 0.97

    interest = _extract_interest(lowered)
    if interest is not None:
        slots["interest"] = interest
        confidence["interest"] = 0.92

    employment = normalize_employment_type(lowered)
    if employment is not None:
        slots["employment_type"] = employment
        confidence["employment_type"] = 0.94

    if state == "awaiting_monthly_income" or any(
        marker in lowered for marker in ["salary", "income", "earn", "per month", "monthly", "take home", "in hand"]
    ):
        income = normalize_currency_inr(lowered)
        if income is not None:
            slots["monthly_income"] = income
            confidence["monthly_income"] = 0.92

    if state == "awaiting_loan_amount" or any(
        marker in lowered for marker in ["loan amount", "amount", "need", "required", "chahiye", "want loan"]
    ):
        amount = normalize_currency_inr(lowered)
        if amount is not None:
            slots["loan_amount"] = amount
            confidence["loan_amount"] = 0.91

    city = _extract_city(text, state)
    if city is not None:
        slots["city"] = city
        confidence["city"] = 0.88

    age = _extract_age(text)
    if age is not None:
        slots["age"] = age
        confidence["age"] = 0.87

    work_experience_months = _extract_duration_months(text, "work")
    if work_experience_months is not None:
        slots["work_experience_months"] = work_experience_months
        confidence["work_experience_months"] = 0.82

    business_vintage_months = _extract_duration_months(text, "business")
    if business_vintage_months is not None:
        slots["business_vintage_months"] = business_vintage_months
        confidence["business_vintage_months"] = 0.82

    existing_monthly_emi = _extract_existing_emi(text)
    if existing_monthly_emi is not None:
        slots["existing_monthly_emi"] = existing_monthly_emi
        confidence["existing_monthly_emi"] = 0.84

    loan_purpose = _extract_loan_purpose(text)
    if loan_purpose is not None:
        slots["loan_purpose"] = loan_purpose
        confidence["loan_purpose"] = 0.8

    return slots, confidence, flags


def _merge_slots(session: CallSession, slots: dict[str, object], confidence: dict[str, float]) -> None:
    for key, value in slots.items():
        session.slots[key] = value
        existing = session.slot_confidence.get(key, 0.0)
        session.slot_confidence[key] = max(existing, confidence.get(key, 0.0))


def _fallback_prompt_for_state(state: str, language: str) -> str:
    mapping = {
        "awaiting_consent": "clarify_consent",
        "awaiting_interest": "clarify_interest",
        "awaiting_employment_type": "clarify_employment_type",
        "awaiting_monthly_income": "clarify_monthly_income",
        "awaiting_loan_amount": "clarify_loan_amount",
        "awaiting_city": "clarify_city",
        "awaiting_callback_time": "busy_callback",
    }
    key = mapping.get(state, "clarify_interest")
    return _prompt(key, language)


def _advance(session: CallSession) -> str:
    language = session.language

    if session.slots.get("consent") is False:
        session.state = "completed"
        session.qualification_status = "do_not_contact"
        session.call_status = "do_not_contact"
        return _prompt("do_not_contact", language)

    if session.slots.get("consent") is None:
        session.state = "awaiting_consent"
        session.call_status = "in_progress"
        return _prompt("ask_consent", language)

    if session.slots.get("interest") is False:
        session.state = "completed"
        session.qualification_status = "not_interested"
        session.call_status = "not_interested"
        return _prompt("not_interested", language)

    if session.slots.get("interest") is None:
        session.state = "awaiting_interest"
        session.call_status = "in_progress"
        return _prompt("ask_interest", language)

    if session.slots.get("employment_type") is None:
        session.state = "awaiting_employment_type"
        session.call_status = "in_progress"
        return _prompt("ask_employment_type", language)

    if session.slots.get("monthly_income") is None:
        session.state = "awaiting_monthly_income"
        session.call_status = "in_progress"
        return _prompt("ask_monthly_income", language)

    if session.slots.get("loan_amount") is None:
        session.state = "awaiting_loan_amount"
        session.call_status = "in_progress"
        return _prompt("ask_loan_amount", language)

    if session.slots.get("city") is None:
        session.state = "awaiting_city"
        session.call_status = "in_progress"
        return _prompt("ask_city", language)

    normalized_slots, status, _, _ = evaluate_personal_loan(session.slots)
    session.slots.update(normalized_slots)

    if status == "qualified":
        session.state = "completed"
        session.qualification_status = "qualified"
        session.call_status = "qualified"
        return _prompt("qualified", language)

    if status == "not_qualified":
        session.state = "completed"
        session.qualification_status = "not_qualified"
        session.call_status = "not_qualified"
        return _prompt("not_qualified", language)

    session.state = "awaiting_interest"
    session.call_status = "in_progress"
    return _prompt("ask_interest", language)


def start_personal_loan_conversation() -> StartConversationResponse:
    session = create_session(product="personal_loan")
    session.slots["language"] = session.language
    session.slot_confidence["language"] = 1.0
    assistant_text = _prompt("opening", session.language)
    _append_turn(session, "assistant", assistant_text)
    save_session(session)

    return StartConversationResponse(
        session_id=session.session_id,
        state=session.state,
        detected_language=session.language,
        assistant_text=assistant_text,
        qualification_status=session.qualification_status,
        call_status=session.call_status,
    )


def process_personal_loan_turn(request: ConversationTurnRequest) -> ConversationTurnResponse:
    session = get_session(request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    started = time.perf_counter()
    user_text = request.user_text.strip()

    if not user_text:
        session.fallback_count += 1
        assistant_text = _fallback_prompt_for_state(session.state, session.language)
        _append_turn(session, "assistant", assistant_text)
        session.last_latency_ms = round((time.perf_counter() - started) * 1000, 2)
        save_session(session)
        return ConversationTurnResponse(
            session_id=session.session_id,
            state=session.state,
            detected_language=session.language,
            assistant_text=assistant_text,
            qualification_status=session.qualification_status,
            call_status=session.call_status,
            normalized_slots=session.slots,
            slot_confidence=session.slot_confidence,
            fallback_count=session.fallback_count,
            last_latency_ms=session.last_latency_ms,
        )

    _append_turn(session, "user", user_text)

    previous_language = session.language
    session.language = _detect_language(user_text, session.language)
    language_changed = previous_language != session.language
    session.slots["language"] = session.language
    session.slot_confidence["language"] = 1.0

    lowered = user_text.lower()

    if contains_sensitive_financial_input(user_text):
        assistant_text = _prompt("sensitive_redirect", session.language)
        _append_turn(session, "assistant", assistant_text)
        session.last_latency_ms = round((time.perf_counter() - started) * 1000, 2)
        save_session(session)
        return ConversationTurnResponse(
            session_id=session.session_id,
            state=session.state,
            detected_language=session.language,
            assistant_text=assistant_text,
            qualification_status=session.qualification_status,
            call_status=session.call_status,
            normalized_slots=session.slots,
            slot_confidence=session.slot_confidence,
            fallback_count=session.fallback_count,
            last_latency_ms=session.last_latency_ms,
        )

    slots, confidence, flags = _extract_slots(user_text, session.state)

    if flags["human"]:
        session.state = "completed"
        session.qualification_status = "escalated_to_human"
        session.call_status = "escalated"
        session.fallback_count = 0
        assistant_text = _prompt("human_handoff", session.language)
        _append_turn(session, "assistant", assistant_text)
        session.last_latency_ms = round((time.perf_counter() - started) * 1000, 2)
        save_session(session)
        return ConversationTurnResponse(
            session_id=session.session_id,
            state=session.state,
            detected_language=session.language,
            assistant_text=assistant_text,
            qualification_status=session.qualification_status,
            call_status=session.call_status,
            normalized_slots=session.slots,
            slot_confidence=session.slot_confidence,
            fallback_count=session.fallback_count,
            last_latency_ms=session.last_latency_ms,
        )

    if session.state == "awaiting_callback_time":
        session.slots["callback_time"] = user_text
        session.slot_confidence["callback_time"] = 0.75
        session.state = "completed"
        session.qualification_status = "callback_requested"
        session.call_status = "callback_scheduled"
        session.fallback_count = 0
        assistant_text = _prompt("callback_scheduled", session.language)
        _append_turn(session, "assistant", assistant_text)
        session.last_latency_ms = round((time.perf_counter() - started) * 1000, 2)
        save_session(session)
        return ConversationTurnResponse(
            session_id=session.session_id,
            state=session.state,
            detected_language=session.language,
            assistant_text=assistant_text,
            qualification_status=session.qualification_status,
            call_status=session.call_status,
            normalized_slots=session.slots,
            slot_confidence=session.slot_confidence,
            fallback_count=session.fallback_count,
            last_latency_ms=session.last_latency_ms,
        )

    if flags["busy"]:
        session.state = "awaiting_callback_time"
        session.call_status = "busy"
        session.fallback_count = 0
        assistant_text = _prompt("busy_callback", session.language)
        _append_turn(session, "assistant", assistant_text)
        session.last_latency_ms = round((time.perf_counter() - started) * 1000, 2)
        save_session(session)
        return ConversationTurnResponse(
            session_id=session.session_id,
            state=session.state,
            detected_language=session.language,
            assistant_text=assistant_text,
            qualification_status=session.qualification_status,
            call_status=session.call_status,
            normalized_slots=session.slots,
            slot_confidence=session.slot_confidence,
            fallback_count=session.fallback_count,
            last_latency_ms=session.last_latency_ms,
        )

    progress = bool(slots) or language_changed
    if slots:
        _merge_slots(session, slots, confidence)

    if not progress:
        session.fallback_count += 1
        if session.fallback_count >= 3:
            session.state = "completed"
            session.qualification_status = "escalated_to_human"
            session.call_status = "escalated"
            assistant_text = _prompt("fallback_escalate", session.language)
        else:
            assistant_text = _fallback_prompt_for_state(session.state, session.language)

        _append_turn(session, "assistant", assistant_text)
        session.last_latency_ms = round((time.perf_counter() - started) * 1000, 2)
        save_session(session)
        return ConversationTurnResponse(
            session_id=session.session_id,
            state=session.state,
            detected_language=session.language,
            assistant_text=assistant_text,
            qualification_status=session.qualification_status,
            call_status=session.call_status,
            normalized_slots=session.slots,
            slot_confidence=session.slot_confidence,
            fallback_count=session.fallback_count,
            last_latency_ms=session.last_latency_ms,
        )

    session.fallback_count = 0
    assistant_text = _advance(session)
    _append_turn(session, "assistant", assistant_text)
    session.last_latency_ms = round((time.perf_counter() - started) * 1000, 2)
    save_session(session)

    return ConversationTurnResponse(
        session_id=session.session_id,
        state=session.state,
        detected_language=session.language,
        assistant_text=assistant_text,
        qualification_status=session.qualification_status,
        call_status=session.call_status,
        normalized_slots=session.slots,
        slot_confidence=session.slot_confidence,
        fallback_count=session.fallback_count,
        last_latency_ms=session.last_latency_ms,
    )


def get_personal_loan_session(session_id: str) -> SessionDetailResponse:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionDetailResponse(session=session)


def list_personal_loan_sessions() -> list[CallSession]:
    return list_sessions()