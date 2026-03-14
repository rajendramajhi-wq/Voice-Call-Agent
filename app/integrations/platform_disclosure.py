from app.core.config import get_settings
from app.domain.provider_models import PlatformComponent, PlatformDisclosure


def get_platform_disclosure() -> PlatformDisclosure:
    settings = get_settings()

    return PlatformDisclosure(
        product="personal_loan",
        orchestration=PlatformComponent(
            provider="vapi",
            model=None,
            notes="Outbound calling orchestration and server webhooks",
        ),
        llm=PlatformComponent(
            provider="openai",
            model=settings.openai_model,
            notes=f"Temperature={settings.openai_temperature}",
        ),
        tts=PlatformComponent(
            provider="elevenlabs",
            model=settings.elevenlabs_model_id,
            notes=f"Voice ID={settings.elevenlabs_voice_id or 'not_set'}",
        ),
        transcriber=PlatformComponent(
            provider=settings.vapi_transcriber_provider,
            model=settings.vapi_transcriber_model,
            notes="Configured via Vapi assistant payload",
        ),
        webhook_url=f"{settings.app_base_url.rstrip('/')}/api/v1/providers/vapi/webhook",
        local_mode=True,
    )