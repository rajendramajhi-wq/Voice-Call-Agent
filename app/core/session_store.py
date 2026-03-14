from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.domain.models import CallSession


_SESSION_STORE: dict[str, CallSession] = {}
_LOCK = Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session(product: str = "personal_loan") -> CallSession:
    now = _utc_now_iso()
    session = CallSession(
        session_id=uuid4().hex,
        product=product,
        state="awaiting_consent",
        started_at=now,
        updated_at=now,
    )
    with _LOCK:
        _SESSION_STORE[session.session_id] = session
    return session


def get_session(session_id: str) -> CallSession | None:
    with _LOCK:
        return _SESSION_STORE.get(session_id)


def save_session(session: CallSession) -> CallSession:
    session.updated_at = _utc_now_iso()
    with _LOCK:
        _SESSION_STORE[session.session_id] = session
    return session


def list_sessions() -> list[CallSession]:
    with _LOCK:
        return list(_SESSION_STORE.values())