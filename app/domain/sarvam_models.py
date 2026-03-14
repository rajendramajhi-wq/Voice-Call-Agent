from pydantic import BaseModel


class SarvamTTSRequest(BaseModel):
    text: str
    language_code: str = "en-IN"
    speaker: str | None = None
    filename_prefix: str = "sarvam_preview"


class SarvamTTSResponse(BaseModel):
    output_path: str
    bytes_written: int
    language_code: str
    speaker: str
    model: str