from app.api.routes.conversation import router as conversation_router
from app.api.routes.health import router as health_router
from app.api.routes.personal_loan import router as personal_loan_router
from app.api.routes.providers import router as providers_router
from app.api.routes.sarvam import router as sarvam_router

__all__ = [
    "health_router",
    "personal_loan_router",
    "conversation_router",
    "providers_router",
    "sarvam_router",
]

