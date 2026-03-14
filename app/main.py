import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    conversation_router,
    health_router,
    personal_loan_router,
    providers_router,
    sarvam_router,
)


from app.core.config import get_settings
from app.core.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="0.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sarvam_router)


@app.on_event("startup")
def on_startup():
    logger.info("Starting %s in %s mode", settings.app_name, settings.app_env)


@app.get("/")
def root():
    return {
        "message": f"{settings.app_name} is running",
        "environment": settings.app_env,
        "product": settings.default_product,
    }


app.include_router(health_router)
app.include_router(personal_loan_router)
app.include_router(conversation_router)
app.include_router(providers_router)