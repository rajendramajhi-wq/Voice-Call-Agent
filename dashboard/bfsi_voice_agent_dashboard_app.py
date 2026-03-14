import json
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st


st.set_page_config(
    page_title="BFSI Voice Agent Dashboard",
    page_icon="📞",
    layout="wide",
)

BACKEND_DEFAULT = "http://127.0.0.1:8000"
ARTIFACTS_DEFAULT = "artifacts"
PRODUCTS = [
    "Unknown / Auto-detect",
    "Home Loan",
    "Personal Loan",
    "Unsecured Loan",
    "Loan Against Property",
    "Gold Loan",
    "Commercial Vehicle Loan",
    "Four Wheeler Loan",
    "Education Loan",
    "MSME Business Loan",
    "Credit Card",
]
LANGUAGES = ["Auto", "English", "Hindi", "Hindi-English"]


# ---------- Styling ----------
st.markdown(
    """
    <style>
        .block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
        div[data-testid="stMetric"] {
            background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
            border: 1px solid #e2e8f0;
            padding: 12px 14px;
            border-radius: 16px;
        }
        .app-section {
            padding: 0.75rem 0 0.25rem 0;
        }
        .muted {
            color: #64748b;
            font-size: 0.92rem;
        }
        .pill {
            display: inline-block;
            padding: 0.2rem 0.55rem;
            border-radius: 999px;
            background: #eff6ff;
            color: #1d4ed8;
            font-size: 0.78rem;
            margin-right: 0.4rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- Request helpers ----------
def _requests_session() -> requests.Session:
    if "http_session" not in st.session_state:
        st.session_state.http_session = requests.Session()
    return st.session_state.http_session


def get_json(url: str, timeout: int = 20) -> Any:
    response = _requests_session().get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def post_json(url: str, payload: dict | None = None, timeout: int = 60) -> Any:
    response = _requests_session().post(url, json=payload or {}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def safe_get_json(url: str, timeout: int = 20):
    try:
        return get_json(url, timeout=timeout), None
    except Exception as exc:
        return None, str(exc)


def safe_post_json(url: str, payload: dict | None = None, timeout: int = 60):
    try:
        return post_json(url, payload=payload, timeout=timeout), None
    except Exception as exc:
        return None, str(exc)


# ---------- State helpers ----------
def init_state() -> None:
    st.session_state.setdefault("recent_launches", [])
    st.session_state.setdefault("watch_session_id", "")
    st.session_state.setdefault("watch_call_id", "")
    st.session_state.setdefault("watch_label", "")


init_state()


# ---------- Data helpers ----------
def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    raw = str(value).strip()
    if not raw:
        return None

    candidates = [
        raw,
        raw.replace("Z", "+00:00"),
    ]
    for item in candidates:
        try:
            return datetime.fromisoformat(item)
        except Exception:
            pass

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%d-%m-%Y %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except Exception:
            continue
    return None


def fmt_dt(value: Any) -> str:
    dt = parse_dt(value)
    return dt.strftime("%d %b %Y, %I:%M:%S %p") if dt else (str(value) if value else "-")


def format_seconds(total_seconds: Any) -> str:
    try:
        sec = int(float(total_seconds or 0))
    except Exception:
        return "0s"

    hours = sec // 3600
    minutes = (sec % 3600) // 60
    seconds = sec % 60
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def mask_phone(number: Any) -> str:
    raw = str(number or "")
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 4:
        return raw or "-"
    return f"*** *** {digits[-4:]}"


def get_transcript_list(session: dict) -> list[dict]:
    transcript = session.get("transcript") or []
    return transcript if isinstance(transcript, list) else []


def get_transcript_preview(session: dict, limit: int = 180) -> str:
    transcript = get_transcript_list(session)
    if transcript:
        merged = " ".join(str(turn.get("masked_text") or "") for turn in transcript).strip()
        return merged[:limit] + ("..." if len(merged) > limit else "") if merged else "No transcript yet"
    text = str(session.get("transcript_text") or session.get("last_message") or "").strip()
    if not text:
        return "No transcript yet"
    return text[:limit] + ("..." if len(text) > limit else "")


def get_product(session: dict) -> str:
    slots = session.get("slots") or {}
    product = (
        session.get("product")
        or slots.get("product")
        or slots.get("loan_product")
        or slots.get("selected_product")
        or "Unknown"
    )
    return str(product)


def get_duration_seconds(session: dict) -> int:
    candidates = [
        session.get("duration_seconds"),
        session.get("call_duration_seconds"),
        session.get("duration_sec"),
        session.get("call_duration_sec"),
        session.get("duration"),
    ]
    for value in candidates:
        if value is None:
            continue
        try:
            return int(float(value))
        except Exception:
            continue

    transcript = get_transcript_list(session)
    if len(transcript) >= 2:
        first_ts = parse_dt(transcript[0].get("timestamp"))
        last_ts = parse_dt(transcript[-1].get("timestamp"))
        if first_ts and last_ts:
            diff = int((last_ts - first_ts).total_seconds())
            return max(diff, 0)
    return 0


def get_avg_confidence(session: dict) -> float | None:
    direct_candidates = [
        session.get("confidence"),
        session.get("overall_confidence"),
        session.get("average_confidence"),
        session.get("avg_confidence"),
    ]
    for value in direct_candidates:
        try:
            numeric = float(value)
            if 0 <= numeric <= 1:
                return numeric
            if 1 < numeric <= 100:
                return numeric / 100.0
        except Exception:
            continue

    slot_confidence = session.get("slot_confidence") or {}
    numeric_values: list[float] = []
    if isinstance(slot_confidence, dict):
        for value in slot_confidence.values():
            try:
                numeric = float(value)
                if 0 <= numeric <= 1:
                    numeric_values.append(numeric)
                elif 1 < numeric <= 100:
                    numeric_values.append(numeric / 100.0)
            except Exception:
                continue

    if numeric_values:
        return sum(numeric_values) / len(numeric_values)
    return None


def get_call_status_bucket(session: dict) -> str:
    call_status = str(session.get("call_status") or "").strip().lower()
    state = str(session.get("state") or "").strip().lower()
    transcript = get_transcript_list(session)

    if call_status in {"busy", "user_busy"}:
        return "busy"

    if call_status in {
        "not_picked",
        "not picked",
        "no_answer",
        "missed",
        "no_connect",
        "not_connected",
        "failed",
        "ring_timeout",
    }:
        return "not_picked"

    if call_status in {
        "picked",
        "answered",
        "connected",
        "completed",
        "callback_scheduled",
        "in_progress",
        "transferred",
    }:
        return "picked"

    if transcript or state in {"active", "completed", "in_progress", "processing"}:
        return "picked"

    return "unknown"


def get_qualification_outcome(session: dict) -> str:
    value = str(session.get("qualification_status") or "unknown").strip().lower()
    if not value or value == "unknown":
        return "unknown"
    return value


def summarize_sessions(sessions: list[dict]) -> dict[str, float]:
    total = len(sessions)
    picked = sum(1 for s in sessions if get_call_status_bucket(s) == "picked")
    busy = sum(1 for s in sessions if get_call_status_bucket(s) == "busy")
    not_picked = sum(1 for s in sessions if get_call_status_bucket(s) == "not_picked")
    qualified = sum(1 for s in sessions if get_qualification_outcome(s) == "qualified")
    escalated = sum(
        1
        for s in sessions
        if get_qualification_outcome(s) in {"escalated_to_human", "escalate_to_human", "human_callback"}
    )
    completed = sum(1 for s in sessions if str(s.get("state") or "").lower() == "completed")
    active = sum(1 for s in sessions if str(s.get("state") or "").lower() in {"started", "active", "in_progress", "processing"})

    durations = [get_duration_seconds(s) for s in sessions if get_duration_seconds(s) > 0]
    avg_duration = sum(durations) / len(durations) if durations else 0
    success_rate = (qualified / picked * 100) if picked else 0

    return {
        "total": total,
        "picked": picked,
        "busy": busy,
        "not_picked": not_picked,
        "qualified": qualified,
        "escalated": escalated,
        "completed": completed,
        "active": active,
        "avg_duration": avg_duration,
        "success_rate": success_rate,
    }


def session_to_row(session: dict) -> dict[str, Any]:
    confidence = get_avg_confidence(session)
    timestamp = session.get("started_at") or session.get("created_at") or session.get("updated_at")

    return {
        "session_id": session.get("session_id") or "",
        "external_call_id": session.get("external_call_id") or "",
        "product": get_product(session),
        "call_timestamp": fmt_dt(timestamp),
        "status": get_call_status_bucket(session),
        "call_duration_seconds": get_duration_seconds(session),
        "call_duration": format_seconds(get_duration_seconds(session)),
        "qualification_outcome": get_qualification_outcome(session),
        "confidence_score": round(confidence * 100, 1) if confidence is not None else None,
        "language": session.get("language") or "unknown",
        "state": session.get("state") or "unknown",
        "customer_number": mask_phone(session.get("customer_number")),
        "updated_at": fmt_dt(session.get("updated_at")),
        "transcript": get_transcript_preview(session),
    }


def build_sessions_df(sessions: list[dict]) -> pd.DataFrame:
    rows = [session_to_row(s) for s in sessions]
    if not rows:
        return pd.DataFrame(
            columns=[
                "session_id",
                "external_call_id",
                "product",
                "call_timestamp",
                "status",
                "call_duration",
                "qualification_outcome",
                "confidence_score",
                "language",
                "state",
                "customer_number",
                "updated_at",
                "transcript",
            ]
        )
    return pd.DataFrame(rows)


def filter_session_rows(
    df: pd.DataFrame,
    search_text: str,
    product_filter: str,
    language_filter: str,
    status_filter: str,
    qualification_filter: str,
) -> pd.DataFrame:
    out = df.copy()

    if product_filter != "All":
        out = out[out["product"] == product_filter]
    if language_filter != "All":
        out = out[out["language"] == language_filter]
    if status_filter != "All":
        out = out[out["status"] == status_filter]
    if qualification_filter != "All":
        out = out[out["qualification_outcome"] == qualification_filter]

    if search_text.strip() and not out.empty:
        q = search_text.strip().lower()
        mask = (
            out["session_id"].astype(str).str.lower().str.contains(q)
            | out["external_call_id"].astype(str).str.lower().str.contains(q)
            | out["customer_number"].astype(str).str.lower().str.contains(q)
            | out["product"].astype(str).str.lower().str.contains(q)
            | out["transcript"].astype(str).str.lower().str.contains(q)
        )
        out = out[mask]

    return out


def count_frame(df: pd.DataFrame, column: str, label_name: str = "label") -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return pd.DataFrame(columns=[label_name, "count"])
    vc = df[column].fillna("unknown").astype(str).value_counts().reset_index()
    vc.columns = [label_name, "count"]
    return vc


def get_call_artifact_dirs(artifacts_root: str) -> list[Path]:
    base = Path(artifacts_root) / "call_artifacts"
    if not base.exists():
        return []
    return sorted([p for p in base.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True)


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def find_audio_files(call_dir: Path) -> list[Path]:
    audio_exts = {".mp3", ".wav", ".m4a", ".ogg", ".webm", ".aac", ".flac", ".bin"}
    return sorted([p for p in call_dir.iterdir() if p.is_file() and p.suffix.lower() in audio_exts])


def guess_audio_format(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".webm": "audio/webm",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".flac": "audio/flac",
    }.get(suffix, "audio/mpeg")


def latest_artifact_for_call(artifacts_root: str, call_id: str | None) -> Path | None:
    if not call_id:
        return None
    candidate = Path(artifacts_root) / "call_artifacts" / str(call_id)
    return candidate if candidate.exists() else None


def artifact_summary(call_dir: Path) -> dict[str, Any]:
    return {
        "folder": call_dir.name,
        "has_artifact_json": (call_dir / "artifact.json").exists(),
        "has_transcript": (call_dir / "transcript.txt").exists(),
        "has_messages": (call_dir / "messages.json").exists(),
        "audio_files": [p.name for p in find_audio_files(call_dir)],
    }


def render_transcript(session: dict) -> None:
    transcript = get_transcript_list(session)
    if not transcript:
        st.info("No transcript stored in the session yet.")
        return

    for idx, turn in enumerate(transcript, start=1):
        speaker = str(turn.get("speaker") or "unknown").title()
        text = str(turn.get("masked_text") or turn.get("text") or "").strip() or "-"
        timestamp = fmt_dt(turn.get("timestamp"))
        with st.container(border=True):
            c1, c2 = st.columns([0.8, 0.2])
            c1.markdown(f"**{idx}. {speaker}**")
            c2.caption(timestamp)
            st.write(text)


def render_call_detail(session: dict, artifacts_root: str) -> None:
    duration_sec = get_duration_seconds(session)
    confidence = get_avg_confidence(session)
    external_call_id = session.get("external_call_id")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Product", get_product(session))
    m2.metric("Call status", get_call_status_bucket(session))
    m3.metric("Qualification", get_qualification_outcome(session))
    m4.metric("Duration", format_seconds(duration_sec))

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Language", str(session.get("language") or "unknown"))
    s2.metric("State", str(session.get("state") or "unknown"))
    s3.metric("Confidence", f"{round(confidence * 100, 1)}%" if confidence is not None else "-")
    s4.metric("Call ID", str(external_call_id or "-"))

    st.markdown("### Transcript")
    render_transcript(session)

    st.markdown("### Captured slots")
    left, right = st.columns(2)
    with left:
        st.json(session.get("slots") or {})
    with right:
        st.json(session.get("slot_confidence") or {})

    linked_artifact = latest_artifact_for_call(artifacts_root, external_call_id)
    st.markdown("### Linked artifact")
    if linked_artifact:
        st.success(f"Artifact folder found: {linked_artifact.name}")
        st.json(artifact_summary(linked_artifact))
        audio_files = find_audio_files(linked_artifact)
        if audio_files:
            st.markdown("**Masked audio snippets / recording replay**")
            for audio_file in audio_files:
                st.write(audio_file.name)
                st.audio(str(audio_file), format=guess_audio_format(audio_file))
    else:
        st.info("No local artifact folder matched this session's external call ID yet.")

    with st.expander("Raw session JSON"):
        st.json(session)


def add_recent_launch(item: dict) -> None:
    launches = st.session_state.recent_launches
    launches.insert(0, item)
    st.session_state.recent_launches = launches[:20]


def resolve_session(sessions: list[dict], session_id: str = "", external_call_id: str = "") -> dict | None:
    if session_id:
        for session in sessions:
            if str(session.get("session_id") or "") == str(session_id):
                return session
    if external_call_id:
        for session in sessions:
            if str(session.get("external_call_id") or "") == str(external_call_id):
                return session
    return None


def try_health(base_url: str) -> tuple[Any, str | None]:
    return safe_get_json(f"{base_url}/health", timeout=10)


# ---------- Sidebar ----------
with st.sidebar:
    st.title("📞 BFSI Voice Agent")
    base_url = st.text_input("Backend URL", value=BACKEND_DEFAULT)
    artifacts_root = st.text_input("Artifacts folder", value=ARTIFACTS_DEFAULT)

    st.divider()
    auto_refresh = st.checkbox("Auto refresh", value=False)
    refresh_seconds = st.slider("Refresh every (seconds)", min_value=5, max_value=60, value=10, step=5)

    if st.button("Refresh now", use_container_width=True):
        st.rerun()

    health_data, health_error = try_health(base_url)
    if health_error:
        st.warning("Backend health check unavailable")
        st.caption(health_error)
    else:
        status = health_data.get("status") if isinstance(health_data, dict) else "ok"
        st.success(f"Backend health: {status}")

    st.caption("This console reads live backend APIs and local saved artifacts.")

if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()


# ---------- Data load ----------
sessions_data, sessions_error = safe_get_json(f"{base_url}/api/v1/conversation/sessions")
disclosure_data, disclosure_error = safe_get_json(f"{base_url}/api/v1/providers/disclosure")
sessions = sessions_data if isinstance(sessions_data, list) else []
sessions_df = build_sessions_df(sessions)
metrics = summarize_sessions(sessions)


# ---------- Header ----------
st.title("BFSI Voice Agent Dashboard")
st.caption(
    "Outbound call command center for live call launch, call connect tracking, transcripts, qualification, recordings, and provider inspection."
)

st.markdown(
    "<div class='app-section'><span class='pill'>Live sessions</span><span class='pill'>Call connect monitor</span><span class='pill'>Masked replay</span><span class='pill'>Compliance-first logs</span></div>",
    unsafe_allow_html=True,
)

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Total sessions", metrics["total"])
m2.metric("Active", metrics["active"])
m3.metric("Picked", metrics["picked"])
m4.metric("Qualified", metrics["qualified"])
m5.metric("Success rate", f"{metrics['success_rate']:.1f}%")
m6.metric("Avg handling time", format_seconds(metrics["avg_duration"]))

if sessions_error:
    st.error(f"Could not load sessions: {sessions_error}")


overview_tab, launch_tab, sessions_tab, artifacts_tab, providers_tab = st.tabs(
    ["Overview", "Launch & Call Connect", "Sessions", "Call Artifacts", "Providers"]
)


# ---------- Overview ----------
with overview_tab:
    st.subheader("Operator overview")
    left, right = st.columns([1.5, 1])

    with left:
        search_text = st.text_input("Search by session ID, call ID, phone, product, or transcript")
        c1, c2, c3, c4 = st.columns(4)
        product_values = ["All"] + sorted({str(v) for v in sessions_df["product"].fillna("Unknown").tolist()}) if not sessions_df.empty else ["All"]
        language_values = ["All"] + sorted({str(v) for v in sessions_df["language"].fillna("unknown").tolist()}) if not sessions_df.empty else ["All"]
        status_values = ["All"] + sorted({str(v) for v in sessions_df["status"].fillna("unknown").tolist()}) if not sessions_df.empty else ["All"]
        qualification_values = ["All"] + sorted({str(v) for v in sessions_df["qualification_outcome"].fillna("unknown").tolist()}) if not sessions_df.empty else ["All"]

        product_filter = c1.selectbox("Product", product_values)
        language_filter = c2.selectbox("Language", language_values)
        status_filter = c3.selectbox("Status", status_values)
        qualification_filter = c4.selectbox("Qualification", qualification_values)

        filtered_df = filter_session_rows(
            sessions_df,
            search_text,
            product_filter,
            language_filter,
            status_filter,
            qualification_filter,
        )
        st.caption(f"{len(filtered_df)} / {len(sessions_df)} sessions shown")

        visible_cols = [
            "session_id",
            "external_call_id",
            "product",
            "call_timestamp",
            "status",
            "call_duration",
            "qualification_outcome",
            "confidence_score",
            "language",
            "customer_number",
            "transcript",
        ]
        st.dataframe(filtered_df[visible_cols], use_container_width=True, hide_index=True)

        if not filtered_df.empty:
            csv_bytes = filtered_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download filtered sessions CSV",
                data=csv_bytes,
                file_name="bfsi_sessions_export.csv",
                mime="text/csv",
                use_container_width=True,
            )

    with right:
        st.markdown("**Calls by product**")
        product_counts = count_frame(sessions_df, "product", label_name="product")
        if not product_counts.empty:
            st.bar_chart(product_counts.set_index("product"))
        else:
            st.info("No session data yet.")

        st.markdown("**Status mix**")
        status_counts = count_frame(sessions_df, "status")
        if not status_counts.empty:
            st.bar_chart(status_counts.set_index("label"))

        st.markdown("**Qualification mix**")
        qual_counts = count_frame(sessions_df, "qualification_outcome")
        if not qual_counts.empty:
            st.bar_chart(qual_counts.set_index("label"))

    st.divider()
    st.subheader("Recent launched calls")
    if st.session_state.recent_launches:
        watch_df = pd.DataFrame(st.session_state.recent_launches)
        st.dataframe(watch_df, use_container_width=True, hide_index=True)
    else:
        st.info("No calls launched from this dashboard yet.")


# ---------- Launch & Call Connect ----------
with launch_tab:
    st.subheader("Create live outbound call")
    st.caption(
        "This launches a real outbound call through your current backend routes, then lets you watch the linked session and artifacts update live."
    )

    form_col, monitor_col = st.columns([1.1, 0.9])

    with form_col:
        with st.form("launch_call_form"):
            customer_number = st.text_input("Customer number", placeholder="+91XXXXXXXXXX")
            customer_name = st.text_input("Customer name (optional)", placeholder="Rajendra")
            product = st.selectbox("Product (operator note)", PRODUCTS)
            language = st.selectbox("Language (operator note)", LANGUAGES)
            create_new_session = st.checkbox("Create and attach a fresh session", value=True)
            manual_session_id = st.text_input("Manual session ID (used only when unchecked)")
            submitted = st.form_submit_button("Launch call", use_container_width=True)

        if submitted:
            if not customer_number.strip():
                st.error("Customer number is required.")
            else:
                session_id = None
                if create_new_session:
                    created, err = safe_post_json(f"{base_url}/api/v1/conversation/start", {})
                    if err:
                        st.error(f"Could not create session: {err}")
                        st.stop()
                    session_id = (created or {}).get("session_id")
                    st.success(f"Session created: {session_id}")
                else:
                    session_id = manual_session_id.strip() or None

                launched, err = safe_post_json(
                    f"{base_url}/api/v1/providers/vapi/outbound-call",
                    {
                        "customer_number": customer_number.strip(),
                        "customer_name": customer_name.strip() or None,
                        "session_id": session_id,
                    },
                )

                if err:
                    st.error(f"Call launch failed: {err}")
                else:
                    call_id = (launched or {}).get("call_id")
                    st.success("Outbound call created successfully.")
                    st.json(launched)

                    item = {
                        "launched_at": fmt_dt(datetime.now()),
                        "session_id": session_id or "",
                        "call_id": call_id or "",
                        "customer": mask_phone(customer_number.strip()),
                        "customer_name": customer_name.strip() or "-",
                        "product": product,
                        "language": language,
                    }
                    add_recent_launch(item)
                    st.session_state.watch_session_id = session_id or ""
                    st.session_state.watch_call_id = call_id or ""
                    st.session_state.watch_label = f"{product} | {mask_phone(customer_number.strip())}"

    with monitor_col:
        st.markdown("### Call connect monitor")
        recent_options = ["Use current watch"]
        recent_lookup: dict[str, dict] = {}
        for launch in st.session_state.recent_launches:
            label = f"{launch.get('launched_at', '-') } | {launch.get('product', '-') } | {launch.get('customer', '-') }"
            recent_options.append(label)
            recent_lookup[label] = launch

        selected_watch = st.selectbox("Pick a recent launch", recent_options)
        if selected_watch != "Use current watch":
            chosen = recent_lookup[selected_watch]
            st.session_state.watch_session_id = chosen.get("session_id", "")
            st.session_state.watch_call_id = chosen.get("call_id", "")
            st.session_state.watch_label = f"{chosen.get('product', '-') } | {chosen.get('customer', '-') }"

        watch_session_id = st.text_input("Watch session ID", value=st.session_state.watch_session_id)
        watch_call_id = st.text_input("Watch call ID", value=st.session_state.watch_call_id)

        if st.button("Load watched call", use_container_width=True):
            st.session_state.watch_session_id = watch_session_id.strip()
            st.session_state.watch_call_id = watch_call_id.strip()
            st.rerun()

        watched_summary = resolve_session(sessions, st.session_state.watch_session_id, st.session_state.watch_call_id)
        if watched_summary:
            detail, detail_error = safe_get_json(
                f"{base_url}/api/v1/conversation/sessions/{watched_summary.get('session_id')}"
            )
            if detail_error:
                st.error(detail_error)
            else:
                session = (detail or {}).get("session", {})
                st.success(f"Watching session: {session.get('session_id')}")
                render_call_detail(session, artifacts_root)
        else:
            st.info("Launch a call or enter a known session/call ID to start live monitoring.")


# ---------- Sessions ----------
with sessions_tab:
    st.subheader("Session explorer")
    if sessions_df.empty:
        st.info("No sessions available yet.")
    else:
        left, right = st.columns([1.05, 0.95])

        with left:
            st.markdown("**Session list**")
            explorer_df = sessions_df[[
                "session_id",
                "external_call_id",
                "product",
                "status",
                "qualification_outcome",
                "call_duration",
                "language",
                "updated_at",
            ]].copy()
            st.dataframe(explorer_df, use_container_width=True, hide_index=True)

            session_ids = sessions_df["session_id"].astype(str).tolist()
            default_index = 0
            if st.session_state.watch_session_id and st.session_state.watch_session_id in session_ids:
                default_index = session_ids.index(st.session_state.watch_session_id)

            selected_session_id = st.selectbox("Choose session", options=session_ids, index=default_index)

        with right:
            detail, detail_error = safe_get_json(f"{base_url}/api/v1/conversation/sessions/{selected_session_id}")
            if detail_error:
                st.error(f"Could not load session detail: {detail_error}")
            else:
                render_call_detail((detail or {}).get("session", {}), artifacts_root)


# ---------- Artifacts ----------
with artifacts_tab:
    st.subheader("Saved call artifacts")
    st.caption("Use this to replay masked audio snippets and inspect stored artifacts for demo evidence.")

    call_dirs = get_call_artifact_dirs(artifacts_root)
    if not call_dirs:
        st.info("No saved call artifacts found yet.")
    else:
        artifact_search = st.text_input("Filter artifact folders by call ID")
        visible_dirs = [p for p in call_dirs if artifact_search.strip().lower() in p.name.lower()] if artifact_search.strip() else call_dirs

        if not visible_dirs:
            st.warning("No artifact folders match your search.")
        else:
            selected_dir = st.selectbox("Choose call artifact folder", options=visible_dirs, format_func=lambda p: p.name)
            artifact_json = selected_dir / "artifact.json"
            transcript_txt = selected_dir / "transcript.txt"
            messages_json = selected_dir / "messages.json"

            st.success(f"Folder selected: {selected_dir.name}")
            st.json(artifact_summary(selected_dir))

            meta_col, audio_col = st.columns([1, 1])
            with meta_col:
                if artifact_json.exists():
                    st.markdown("**Artifact JSON**")
                    st.json(read_json_file(artifact_json))
                if messages_json.exists():
                    st.markdown("**Messages**")
                    st.json(read_json_file(messages_json))
                if transcript_txt.exists():
                    st.markdown("**Transcript text**")
                    transcript_text = transcript_txt.read_text(encoding="utf-8")
                    st.text_area("Transcript", transcript_text, height=260)
                    st.download_button(
                        "Download transcript",
                        data=transcript_text,
                        file_name=f"{selected_dir.name}_transcript.txt",
                        use_container_width=True,
                    )

            with audio_col:
                audio_files = find_audio_files(selected_dir)
                if audio_files:
                    st.markdown("**Recording replay**")
                    for audio_file in audio_files:
                        st.write(audio_file.name)
                        st.audio(str(audio_file), format=guess_audio_format(audio_file))
                        st.download_button(
                            f"Download {audio_file.name}",
                            data=audio_file.read_bytes(),
                            file_name=audio_file.name,
                            use_container_width=True,
                            key=f"download_{selected_dir.name}_{audio_file.name}",
                        )
                else:
                    st.info("No downloaded audio files found in this artifact folder.")


# ---------- Providers ----------
with providers_tab:
    st.subheader("Provider inspection")
    disclosure_payload, _ = safe_get_json(f"{base_url}/api/v1/providers/disclosure")
    assistant_payload, payload_error = safe_post_json(f"{base_url}/api/v1/providers/vapi/assistant-payload", {})
    health_payload, health_error = try_health(base_url)

    left, right = st.columns(2)
    with left:
        st.markdown("**Backend health**")
        if health_error:
            st.error(health_error)
        else:
            st.json(health_payload)

        st.markdown("**Platform disclosure**")
        if disclosure_error:
            st.error(disclosure_error)
        else:
            st.json(disclosure_payload)

    with right:
        st.markdown("**Current Vapi assistant payload**")
        if payload_error:
            st.error(payload_error)
        else:
            st.json(assistant_payload)

    with st.expander("What this dashboard covers for the BFSI brief"):
        st.markdown(
            """
            - Live call launch and call-connect monitoring
            - Filters and analytics by product, status, qualification, and language
            - Required dashboard fields: product, timestamp, status, transcript, duration, qualification outcome, confidence score
            - Masked audio replay from local artifacts
            - Provider disclosure and assistant payload inspection
            """
        )
