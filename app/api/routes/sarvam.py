from fastapi import APIRouter, HTTPException

from app.domain.sarvam_models import SarvamTTSRequest, SarvamTTSResponse
from app.integrations.sarvam_client import synthesize_sarvam_tts

router = APIRouter(prefix="/api/v1/sarvam", tags=["sarvam"])


@router.post("/tts", response_model=SarvamTTSResponse)
def sarvam_tts(request: SarvamTTSRequest):
    try:
        return synthesize_sarvam_tts(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc