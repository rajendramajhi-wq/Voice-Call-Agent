from fastapi import APIRouter

from app.domain.models import (
    CallSession,
    ConversationTurnRequest,
    ConversationTurnResponse,
    SessionDetailResponse,
    StartConversationResponse,
)
from app.domain.personal_loan.dialogue_engine import (
    get_personal_loan_session,
    list_personal_loan_sessions,
    process_personal_loan_turn,
    start_personal_loan_conversation,
)

router = APIRouter(prefix="/api/v1/conversation", tags=["conversation"])


@router.post("/start", response_model=StartConversationResponse)
def start_conversation():
    return start_personal_loan_conversation()


@router.post("/turn", response_model=ConversationTurnResponse)
def turn(request: ConversationTurnRequest):
    return process_personal_loan_turn(request)


@router.get("/sessions", response_model=list[CallSession])
def list_sessions():
    return list_personal_loan_sessions()


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def get_session_detail(session_id: str):
    return get_personal_loan_session(session_id)