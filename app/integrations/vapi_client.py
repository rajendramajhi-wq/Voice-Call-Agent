import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.session_store import get_session, save_session
from app.domain.personal_loan.vapi_config import build_vapi_assistant_payload
from app.domain.provider_models import (
    AssistantPayloadResponse,
    OutboundCallRequest,
    OutboundCallResponse,
    ProviderWebhookResponse,
)


def get_vapi_assistant_payload() -> AssistantPayloadResponse:
    return AssistantPayloadResponse(assistant=build_vapi_assistant_payload())


def create_vapi_outbound_call(request: OutboundCallRequest) -> OutboundCallResponse:
    settings = get_settings()

    if not settings.vapi_api_key:
        raise ValueError("VAPI_API_KEY is not configured")

    payload: dict[str, Any] = {
        "customer": {
            "number": request.customer_number,
        },
        "metadata": {
            "product": "personal_loan",
        },
    }

    if request.customer_name:
        payload["customer"]["name"] = request.customer_name
        payload["metadata"]["customerName"] = request.customer_name

    if request.session_id:
        payload["metadata"]["sessionId"] = request.session_id

    # assistant_id = request.assistant_id or settings.vapi_assistant_id
    # if assistant_id:
    #     payload["assistantId"] = assistant_id
    # else:
    #     payload["assistant"] = build_vapi_assistant_payload()


    assistant_id = request.assistant_id or settings.vapi_assistant_id
    if assistant_id:
        payload["assistantId"] = assistant_id
    else:
        payload["assistant"] = build_vapi_assistant_payload(customer_name=request.customer_name)



    if settings.vapi_phone_number_id:
        payload["phoneNumberId"] = settings.vapi_phone_number_id

    response = httpx.post(
        f"{settings.vapi_base_url.rstrip('/')}/call",
        headers={
            "Authorization": f"Bearer {settings.vapi_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60.0,
    )
    response.raise_for_status()

    data = response.json()

    if request.session_id:
        session = get_session(request.session_id)
        if session is not None:
            session.provider = "vapi"
            session.external_call_id = data.get("id")
            session.customer_number = request.customer_number
            session.call_status = "dialing"
            save_session(session)

    return OutboundCallResponse(
        provider="vapi",
        status="created",
        call_id=data.get("id"),
        raw=data,
    )


def _extract_event_type(payload: dict[str, Any]) -> str | None:
    return (
        payload.get("type")
        or payload.get("message", {}).get("type")
        or payload.get("event")
    )


def _extract_call_block(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("call"), dict):
        return payload["call"]
    return payload


def _update_session_from_event(payload: dict[str, Any]) -> None:
    call_block = _extract_call_block(payload)
    metadata = call_block.get("metadata") or payload.get("metadata") or {}
    session_id = metadata.get("sessionId")

    if not session_id:
        return

    session = get_session(session_id)
    if session is None:
        return

    session.provider = "vapi"
    session.external_call_id = call_block.get("id", session.external_call_id)

    event_type = _extract_event_type(payload) or ""
    lowered = event_type.lower()

    if "busy" in lowered:
        session.call_status = "busy"
    elif "answered" in lowered or "in-progress" in lowered or "in_progress" in lowered:
        session.call_status = "picked"
    elif "ended" in lowered or "completed" in lowered:
        session.call_status = "completed"
    elif "failed" in lowered or "no-answer" in lowered or "no_answer" in lowered:
        session.call_status = "not_picked"

    save_session(session)


def record_vapi_webhook(payload: dict[str, Any]) -> ProviderWebhookResponse:
    settings = get_settings()

    events_dir = Path(settings.artifacts_dir) / "vapi_events"
    events_dir.mkdir(parents=True, exist_ok=True)

    event_type = _extract_event_type(payload)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = events_dir / f"event_{timestamp}.json"

    filename.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    _update_session_from_event(payload)

    return ProviderWebhookResponse(ok=True, event_type=event_type)