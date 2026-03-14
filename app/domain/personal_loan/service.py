from app.domain.models import ProductSpec, QualificationRequest, QualificationResponse
from app.domain.personal_loan.loader import load_product_spec, load_script
from app.domain.personal_loan.qualification_rules import evaluate_personal_loan


def get_personal_loan_spec() -> ProductSpec:
    return load_product_spec()


def get_personal_loan_script():
    return load_script()


def qualify_personal_loan(request: QualificationRequest) -> QualificationResponse:
    normalized_slots, status, reasons, next_step = evaluate_personal_loan(request.slots)

    return QualificationResponse(
        product="personal_loan",
        status=status,
        normalized_slots=normalized_slots,
        reasons=reasons,
        next_step=next_step,
    )