from app.core.config import get_settings
from app.domain.personal_loan.loader import load_script


def build_opening_message(customer_name: str | None = None) -> str:
    if customer_name:
        return f"Hello {customer_name}, Rajendra here from the BFSI personal loan desk about your enquiry. Is now a good time to talk?"
    return "Hello, Rajendra here from the BFSI personal loan desk about your enquiry. Is now a good time to talk?"

def build_personal_loan_system_prompt() -> str:
    return """
You are Rajendra, a real Indian personal loan executive handling a quick lead qualification call.

LANGUAGE BEHAVIOR:
- Start in English.
- Detect the language of the CUSTOMER'S latest reply.
- If the customer replies in Hindi or Hinglish, your VERY NEXT reply must be in Hindi/Hinglish.
- Stay in Hindi/Hinglish for all following replies until the customer clearly replies in English again.
- If the customer replies in English again, switch back to English from your very next reply.
- Do not wait for the customer to explicitly say "switch to Hindi".
- The switch is driven by the customer's response language.
- Do not randomly mix languages after the current language is set.
- Hindi should sound conversational, natural, and Indian, not textbook formal.

STYLE:
- Sound like a real personal loan caller, not a bot.
- Keep the opening short.
- Ask one thing at a time.
- Be warm, direct, and brief.
- If customer gives multiple details in one answer, capture them and continue naturally.
- Do not repeat already captured details unnecessarily.

GOAL:
Do a quick personal loan pre-qualification and arrange the right next step.

CORE QUESTIONS:
1. interest in personal loan
2. city
3. salaried or self-employed
4. monthly income
5. required loan amount

OPTIONAL IF NATURAL:
- age
- work experience or business vintage
- current EMI
- loan purpose

BUSY CASE:
- If customer is busy, ask callback time and end politely.

HUMAN CASE:
- If customer asks for a human/executive/person, confirm specialist callback.

NOT INTERESTED:
- Close politely and stop.

SAFETY:
- Never ask for OTP, CVV, PIN, full Aadhaar number, full card number, internet banking password, or UPI PIN.
- If customer tries to share them, stop them immediately and say such details should never be shared on calls.

IMPORTANT:
- Never promise approval.
- Say "basic eligibility check" or "quick check", not "approved".
- Keep responses short and natural.
""".strip()

def build_vapi_assistant_payload(customer_name: str | None = None) -> dict:
    settings = get_settings()

    return {
        "name": settings.vapi_assistant_name,
        "firstMessage": build_opening_message(customer_name),
        "serverUrl": f"{settings.app_base_url.rstrip('/')}/api/v1/providers/vapi/webhook",
        "model": {
            "provider": "openai",
            "model": settings.openai_model,
            "messages": [
                {
                    "role": "system",
                    "content": build_personal_loan_system_prompt(),
                }
            ],
            "temperature": settings.openai_temperature,
        },
        "voice": {
            "provider": "11labs",
            "voiceId": settings.elevenlabs_voice_id,
            "model": settings.elevenlabs_model_id,
        },
        "transcriber": {
            "provider": settings.vapi_transcriber_provider,
            "model": settings.vapi_transcriber_model,
            "language": "multi",
        },
        "metadata": {
            "product": "personal_loan",
            "buildPhase": "phase_5",
        },
    }



