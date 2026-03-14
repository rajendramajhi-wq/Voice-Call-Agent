from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.domain.provider_models import VoicePreviewRequest, VoicePreviewResponse


def synthesize_voice_preview(request: VoicePreviewRequest) -> VoicePreviewResponse:
    settings = get_settings()

    if not settings.elevenlabs_api_key:
        raise ValueError("ELEVENLABS_API_KEY is not configured")

    if not settings.elevenlabs_voice_id:
        raise ValueError("ELEVENLABS_VOICE_ID is not configured")

    output_dir = Path(settings.artifacts_dir) / "audio_previews"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_prefix = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in request.filename_prefix)
    output_path = output_dir / f"{safe_prefix}_{timestamp}.mp3"

    url = f"{settings.elevenlabs_base_url.rstrip('/')}/v1/text-to-speech/{settings.elevenlabs_voice_id}"

    response = httpx.post(
        url,
        headers={
            "xi-api-key": settings.elevenlabs_api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        params={"output_format": "mp3_44100_128"},
        json={
            "text": request.text,
            "model_id": settings.elevenlabs_model_id,
        },
        timeout=60.0,
    )
    response.raise_for_status()

    output_path.write_bytes(response.content)

    return VoicePreviewResponse(
        voice_id=settings.elevenlabs_voice_id,
        model_id=settings.elevenlabs_model_id,
        output_path=str(output_path),
        bytes_written=len(response.content),
    )