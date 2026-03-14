import base64
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.domain.sarvam_models import SarvamTTSRequest, SarvamTTSResponse


def synthesize_sarvam_tts(request: SarvamTTSRequest) -> SarvamTTSResponse:
    settings = get_settings()

    if not settings.sarvam_api_key:
        raise ValueError("SARVAM_API_KEY is not configured")

    output_dir = Path(settings.artifacts_dir) / "sarvam_previews"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_prefix = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in request.filename_prefix)
    ext = ".wav" if settings.sarvam_tts_audio_format.lower() == "wav" else ".bin"
    output_path = output_dir / f"{safe_prefix}_{timestamp}{ext}"

    speaker = request.speaker or settings.sarvam_tts_speaker

    url = f"{settings.sarvam_base_url.rstrip('/')}/text-to-speech"

    payload = {
        "model": settings.sarvam_tts_model,
        "text": request.text,
        "speaker": speaker,
        "target_language_code": request.language_code,
        "sample_rate": settings.sarvam_tts_sample_rate,
        "output_audio_codec": settings.sarvam_tts_audio_format,
    }

    response = httpx.post(
        url,
        headers={
            "api-subscription-key": settings.sarvam_api_key,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60.0,
    )
    response.raise_for_status()

    data = response.json()
    audios = data.get("audios") or []
    if not audios:
        raise ValueError("Sarvam TTS returned no audio")

    audio_bytes = base64.b64decode(audios[0])
    output_path.write_bytes(audio_bytes)

    return SarvamTTSResponse(
        output_path=str(output_path),
        bytes_written=len(audio_bytes),
        language_code=request.language_code,
        speaker=speaker,
        model=settings.sarvam_tts_model,
    )