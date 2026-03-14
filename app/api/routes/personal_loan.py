from fastapi import APIRouter

from app.domain.models import (
    ProductSpec,
    QualificationRequest,
    QualificationResponse,
    ScriptDefinition,
)
from app.domain.personal_loan.service import (
    get_personal_loan_script,
    get_personal_loan_spec,
    qualify_personal_loan,
)

router = APIRouter(prefix="/api/v1/personal-loan", tags=["personal-loan"])


@router.get("/spec", response_model=ProductSpec)
def get_spec():
    return get_personal_loan_spec()


@router.get("/script", response_model=ScriptDefinition)
def get_script():
    return get_personal_loan_script()


@router.post("/qualify", response_model=QualificationResponse)
def qualify(request: QualificationRequest):
    return qualify_personal_loan(request)