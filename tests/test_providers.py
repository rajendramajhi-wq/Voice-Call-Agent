from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_platform_disclosure():
    response = client.get("/api/v1/providers/disclosure")
    assert response.status_code == 200

    data = response.json()
    assert data["product"] == "personal_loan"
    assert data["orchestration"]["provider"] == "vapi"
    assert data["llm"]["provider"] == "openai"
    assert data["tts"]["provider"] == "elevenlabs"


def test_vapi_assistant_payload():
    response = client.post("/api/v1/providers/vapi/assistant-payload")
    assert response.status_code == 200

    data = response.json()
    assistant = data["assistant"]

    assert assistant["model"]["provider"] == "openai"
    assert assistant["voice"]["provider"] == "11labs"
    assert assistant["metadata"]["product"] == "personal_loan"
    system_prompt = assistant["model"]["messages"][0]["content"]
    assert "English, Hindi, and Hinglish" in system_prompt
    assert "never promise approval" in system_prompt.lower()
    assert assistant["transcriber"]["language"] == "multi"


def test_voice_preview_mocked(monkeypatch):
    from app.api.routes import providers as providers_route_module

    def fake_preview(request):
        class FakeResponse:
            voice_id = "voice_123"
            model_id = "eleven_multilingual_v2"
            output_path = "artifacts/audio_previews/mock.mp3"
            bytes_written = 2048

            def model_dump(self):
                return {
                    "voice_id": self.voice_id,
                    "model_id": self.model_id,
                    "output_path": self.output_path,
                    "bytes_written": self.bytes_written,
                }

        return FakeResponse()

    monkeypatch.setattr(providers_route_module, "synthesize_voice_preview", fake_preview)

    response = client.post(
        "/api/v1/providers/voice/preview",
        json={"text": "Namaste, this is a preview", "filename_prefix": "smoke"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["voice_id"] == "voice_123"
    assert data["bytes_written"] == 2048


def test_outbound_call_mocked(monkeypatch):
    from app.api.routes import providers as providers_route_module

    def fake_call(request):
        class FakeResponse:
            provider = "vapi"
            status = "created"
            call_id = "call_123"
            raw = {"id": "call_123", "type": "outboundPhoneCall"}

            def model_dump(self):
                return {
                    "provider": self.provider,
                    "status": self.status,
                    "call_id": self.call_id,
                    "raw": self.raw,
                }

        return FakeResponse()

    monkeypatch.setattr(providers_route_module, "create_vapi_outbound_call", fake_call)

    response = client.post(
        "/api/v1/providers/vapi/outbound-call",
        json={"customer_number": "+911234567890"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "vapi"
    assert data["call_id"] == "call_123"


def test_vapi_webhook_event_is_saved():
    response = client.post(
        "/api/v1/providers/vapi/webhook",
        json={
            "type": "status-update",
            "call": {
                "id": "call_test_1",
                "metadata": {
                    "sessionId": "missing-session-ok",
                },
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["event_type"] == "status-update"