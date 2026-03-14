from functools import lru_cache
from typing import Annotated
import json

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BFSI Voice Agent"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_base_url: str = "http://127.0.0.1:8000"
    debug: bool = True

    openai_api_key: str = ""
    openai_model: str = "gpt-5.4"
    openai_temperature: float = 0.2

    vapi_api_key: str = ""
    vapi_base_url: str = "https://api.vapi.ai"
    vapi_assistant_id: str = ""
    vapi_phone_number_id: str = ""
    vapi_assistant_name: str = "Rajendra Personal Loan Agent"
    vapi_transcriber_provider: str = "deepgram"
    vapi_transcriber_model: str = "nova-2"
    vapi_webhook_secret: str = ""

    elevenlabs_api_key: str = ""
    elevenlabs_base_url: str = "https://api.elevenlabs.io"
    elevenlabs_voice_id: str = ""
    elevenlabs_model_id: str = "eleven_multilingual_v2"

    artifacts_dir: str = "artifacts"

    default_product: str = "personal_loan"
    default_language: str = "en"
    fallback_language: str = "hi-IN"


# Sarvam Testing
    sarvam_api_key: str = ""
    sarvam_base_url: str = "https://api.sarvam.ai"
    sarvam_tts_model: str = "bulbul:v3"
    sarvam_tts_speaker: str = "shubh"
    sarvam_tts_lang: str = "en-IN"
    sarvam_tts_audio_format: str = "wav"
    sarvam_tts_sample_rate: int = 8000





    allowed_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value):
        if isinstance(value, str):
            value = value.strip()

            if not value:
                return []

            if value.startswith("["):
                parsed = json.loads(value)
                if not isinstance(parsed, list):
                    raise ValueError("ALLOWED_ORIGINS JSON value must be a list")
                return [str(item).strip() for item in parsed if str(item).strip()]

            return [item.strip() for item in value.split(",") if item.strip()]

        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()