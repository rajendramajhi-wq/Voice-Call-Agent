from typing import Any

from pydantic import BaseModel, Field


class PlatformComponent(BaseModel):
    provider: str
    model: str | None = None
    notes: str | None = None


class PlatformDisclosure(BaseModel):
    product: str
    orchestration: PlatformComponent
    llm: PlatformComponent
    tts: PlatformComponent
    transcriber: PlatformComponent
    webhook_url: str
    local_mode: bool = True


class VoicePreviewRequest(BaseModel):
    text: str
    filename_prefix: str = "preview"


class VoicePreviewResponse(BaseModel):
    voice_id: str
    model_id: str
    output_path: str
    bytes_written: int


class AssistantPayloadResponse(BaseModel):
    assistant: dict[str, Any]


class OutboundCallRequest(BaseModel):
    customer_number: str
    customer_name: str | None = None
    session_id: str | None = None
    assistant_id: str | None = None


class OutboundCallResponse(BaseModel):
    provider: str
    status: str
    call_id: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ProviderWebhookResponse(BaseModel):
    ok: bool
    event_type: str | None = None