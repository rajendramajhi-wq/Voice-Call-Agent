from typing import Any, Literal

from pydantic import BaseModel, Field


class IntentDefinition(BaseModel):
    name: str
    description: str
    sample_utterances: list[str]


class SlotDefinition(BaseModel):
    name: str
    description: str
    required: bool
    type: str
    normalization_rule: str
    examples: list[str] = Field(default_factory=list)


class ScriptUtterance(BaseModel):
    language: Literal["en", "hi-IN"]
    text: str
    pause_after: bool = False


class ScriptSection(BaseModel):
    id: str
    name: str
    utterances: list[ScriptUtterance]


class ScriptDefinition(BaseModel):
    product: str
    supported_languages: list[str]
    sections: list[ScriptSection]
    security_rules: list[str]


class ProductSpec(BaseModel):
    product: str
    intents: list[IntentDefinition]
    slots: list[SlotDefinition]
    script: ScriptDefinition
    flow_markdown: str


class QualificationRequest(BaseModel):
    slots: dict[str, Any]


class QualificationResponse(BaseModel):
    product: str
    status: str
    normalized_slots: dict[str, Any]
    reasons: list[str]
    next_step: str


class TranscriptTurn(BaseModel):
    speaker: Literal["assistant", "user"]
    masked_text: str
    timestamp: str


class CallSession(BaseModel):
    session_id: str
    product: str = "personal_loan"
    state: str
    language: Literal["en", "hi-IN"] = "en"
    qualification_status: str = "in_progress"
    call_status: str = "initiated"
    provider: str | None = None
    external_call_id: str | None = None
    customer_number: str | None = None
    slots: dict[str, Any] = Field(default_factory=dict)
    slot_confidence: dict[str, float] = Field(default_factory=dict)
    fallback_count: int = 0
    transcript: list[TranscriptTurn] = Field(default_factory=list)
    last_latency_ms: float | None = None
    started_at: str
    updated_at: str


class StartConversationResponse(BaseModel):
    session_id: str
    state: str
    detected_language: str
    assistant_text: str
    qualification_status: str
    call_status: str


class ConversationTurnRequest(BaseModel):
    session_id: str
    user_text: str


class ConversationTurnResponse(BaseModel):
    session_id: str
    state: str
    detected_language: str
    assistant_text: str
    qualification_status: str
    call_status: str
    normalized_slots: dict[str, Any] = Field(default_factory=dict)
    slot_confidence: dict[str, float] = Field(default_factory=dict)
    fallback_count: int = 0
    last_latency_ms: float | None = None


class SessionDetailResponse(BaseModel):
    session: CallSession