from fastapi import APIRouter, Body, HTTPException

from app.domain.provider_models import (
    AssistantPayloadResponse,
    OutboundCallRequest,
    OutboundCallResponse,
    PlatformDisclosure,
    ProviderWebhookResponse,
    VoicePreviewRequest,
    VoicePreviewResponse,
)
from app.integrations.elevenlabs_client import synthesize_voice_preview
from app.integrations.platform_disclosure import get_platform_disclosure
from app.integrations.vapi_client import (
    create_vapi_outbound_call,
    get_vapi_assistant_payload,
    record_vapi_webhook,
)

router = APIRouter(prefix="/api/v1/providers", tags=["providers"])


@router.get("/disclosure", response_model=PlatformDisclosure)
def disclosure():
    return get_platform_disclosure()


@router.post("/voice/preview", response_model=VoicePreviewResponse)
def voice_preview(request: VoicePreviewRequest):
    try:
        return synthesize_voice_preview(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/vapi/assistant-payload", response_model=AssistantPayloadResponse)
def assistant_payload():
    return get_vapi_assistant_payload()


@router.post("/vapi/outbound-call", response_model=OutboundCallResponse)
def outbound_call(request: OutboundCallRequest):
    try:
        return create_vapi_outbound_call(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/vapi/webhook", response_model=ProviderWebhookResponse)
def vapi_webhook(payload: dict = Body(...)):
    return record_vapi_webhook(payload)