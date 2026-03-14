import json
import time
from datetime import datetime, timezone
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


def get_json(url: str) -> Any:
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.json()


def post_json(url: str, payload: dict | None = None) -> Any:
    response = requests.post(url, json=payload or {}, timeout=60)
    response.raise_for_status()
    return response.json()


def safe_get_json(url: str):
    try:
        return get_json(url), None
    except Exception as exc:
        return None, str(exc)


def safe_post_json(url: str, payload: dict | None = None):
    try:
        return post_json(url, payload), None
    except Exception as exc:
        return None, str(exc)


def load_sessions(base_url: str) -> list[dict]:
    data = get_json(f"{base_url}/api/v1/conversation/sessions")
    return data if isinstance(data, list) else []


def summarize_sessions(sessions: list[dict]) -> dict[str, int]:
    total = len(sessions)
    qualified = sum(1 for s in sessions if s.get("qualification_status") == "qualified")
    escalated = sum(
        1 for s in sessions if s.get("qualification_status") in {"escalated_to_human", "escalate_to_human"}
    )
    callbacks = sum(1 for s in sessions if s.get("call_status") == "callback_scheduled")
    completed = sum(1 for s in sessions if s.get("state") == "completed")
    return {
        "total": total,
        "qualified": qualified,
        "escalated": escalated,
        "callbacks": callbacks,
        "completed": completed,
    }


def flatten_sessions_for_table(sessions: list[dict]) -> pd.DataFrame:
    rows = []
    for s in sessions:
        rows.append(
            {
                "session_id": s.get("session_id"),
                "state": s.get("state"),
                "language": s.get("language"),
                "qualification_status": s.get("qualification_status"),
                "call_status": s.get("call_status"),
                "customer_number": s.get("customer_number"),
                "external_call_id": s.get("external_call_id"),
                "started_at": s.get("started_at"),
                "updated_at": s.get("updated_at"),
            }
        )
    return pd.DataFrame(rows)


def filter_sessions(
    sessions: list[dict],
    search_text: str,
    language_filter: str,
    call_status_filter: str,
    qualification_filter: str,
) -> list[dict]:
    filtered = sessions

    if language_filter != "All":
        filtered = [s for s in filtered if (s.get("language") or "unknown") == language_filter]

    if call_status_filter != "All":
        filtered = [s for s in filtered if (s.get("call_status") or "unknown") == call_status_filter]

    if qualification_filter != "All":
        filtered = [s for s in filtered if (s.get("qualification_status") or "unknown") == qualification_filter]

    if search_text.strip():
        q = search_text.strip().lower()
        filtered = [
            s
            for s in filtered
            if q in str(s.get("session_id", "")).lower()
            or q in str(s.get("external_call_id", "")).lower()
            or q in str(s.get("customer_number", "")).lower()
        ]

    return filtered


def count_by_key(sessions: list[dict], key: str) -> pd.DataFrame:
    counts: dict[str, int] = {}
    for s in sessions:
        value = s.get(key) or "unknown"
        counts[value] = counts.get(value, 0) + 1

    return pd.DataFrame(
        [{"label": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]
    )


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
    if suffix == ".mp3":
        return "audio/mpeg"
    if suffix == ".wav":
        return "audio/wav"
    if suffix == ".ogg":
        return "audio/ogg"
    if suffix == ".webm":
        return "audio/webm"
    if suffix == ".m4a":
        return "audio/mp4"
    if suffix == ".aac":
        return "audio/aac"
    if suffix == ".flac":
        return "audio/flac"
    return "audio/mpeg"


def render_transcript(session: dict):
    transcript = session.get("transcript", [])
    if not transcript:
        st.info("No transcript stored in session yet.")
        return

    for turn in transcript:
        speaker = turn.get("speaker", "unknown").title()
        text = turn.get("masked_text", "")
        timestamp = turn.get("timestamp", "")
        with st.container(border=True):
            st.markdown(f"**{speaker}**")
            st.write(text)
            st.caption(timestamp)


def latest_artifact_for_call(artifacts_root: str, call_id: str | None) -> Path | None:
    if not call_id:
        return None
    candidate = Path(artifacts_root) / "call_artifacts" / call_id
    return candidate if candidate.exists() else None


def artifact_summary(call_dir: Path) -> dict[str, Any]:
    return {
        "folder": call_dir.name,
        "has_artifact_json": (call_dir / "artifact.json").exists(),
        "has_transcript": (call_dir / "transcript.txt").exists(),
        "has_messages": (call_dir / "messages.json").exists(),
        "audio_files": [p.name for p in find_audio_files(call_dir)],
    }


def review_store_path(artifacts_root: str) -> Path:
    base = Path(artifacts_root) / "reviews"
    base.mkdir(parents=True, exist_ok=True)
    return base / "call_reviews.jsonl"


def load_reviews(artifacts_root: str) -> list[dict]:
    path = review_store_path(artifacts_root)
    if not path.exists():
        return []

    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def save_review_entry(artifacts_root: str, review: dict) -> None:
    path = review_store_path(artifacts_root)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(review, ensure_ascii=False) + "\n")


def latest_review_for_session(artifacts_root: str, session_id: str) -> dict | None:
    reviews = load_reviews(artifacts_root)
    matched = [r for r in reviews if r.get("session_id") == session_id]
    if not matched:
        return None
    matched.sort(key=lambda x: x.get("reviewed_at", ""))
    return matched[-1]


def reviews_as_dataframe(artifacts_root: str) -> pd.DataFrame:
    reviews = load_reviews(artifacts_root)
    if not reviews:
        return pd.DataFrame(
            columns=[
                "reviewed_at",
                "session_id",
                "external_call_id",
                "verdict",
                "issues",
                "reviewer_name",
                "notes",
            ]
        )

    rows = []
    for r in reviews:
        rows.append(
            {
                "reviewed_at": r.get("reviewed_at"),
                "session_id": r.get("session_id"),
                "external_call_id": r.get("external_call_id"),
                "verdict": r.get("verdict"),
                "issues": ", ".join(r.get("issues", [])),
                "reviewer_name": r.get("reviewer_name"),
                "notes": r.get("notes"),
            }
        )
    return pd.DataFrame(rows)


with st.sidebar:
    st.title("📞 BFSI Voice Agent")
    base_url = st.text_input("Backend URL", value=BACKEND_DEFAULT)
    artifacts_root = st.text_input("Artifacts folder", value=ARTIFACTS_DEFAULT)

    st.divider()
    auto_refresh = st.checkbox("Auto refresh", value=False)
    refresh_seconds = st.slider("Refresh every (seconds)", min_value=5, max_value=60, value=10, step=5)

    if st.button("Refresh now", use_container_width=True):
        st.rerun()

    st.caption("Reads live backend APIs and local saved artifacts.")

if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()

st.title("BFSI Voice Agent Dashboard")
st.caption("Outbound call console for sessions, qualification, recordings, review, and provider inspection.")

overview_tab, launch_tab, sessions_tab, review_tab, artifacts_tab, providers_tab = st.tabs(
    ["Overview", "Launch Call", "Sessions", "Review", "Call Artifacts", "Providers"]
)

with overview_tab:
    sessions_data, sessions_error = safe_get_json(f"{base_url}/api/v1/conversation/sessions")
    disclosure, disclosure_error = safe_get_json(f"{base_url}/api/v1/providers/disclosure")

    sessions = sessions_data or []
    metrics = summarize_sessions(sessions)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total sessions", metrics["total"])
    m2.metric("Completed", metrics["completed"])
    m3.metric("Qualified", metrics["qualified"])
    m4.metric("Escalated", metrics["escalated"])
    m5.metric("Callbacks", metrics["callbacks"])

    if sessions_error:
        st.error(f"Could not load sessions: {sessions_error}")

    st.divider()

    left, right = st.columns([1.2, 1])

    with left:
        st.subheader("Live session filters")
        f1, f2, f3 = st.columns(3)

        language_values = ["All"] + sorted({s.get("language") or "unknown" for s in sessions})
        call_status_values = ["All"] + sorted({s.get("call_status") or "unknown" for s in sessions})
        qualification_values = ["All"] + sorted({s.get("qualification_status") or "unknown" for s in sessions})

        search_text = st.text_input("Search by session ID, call ID, or phone")
        language_filter = f1.selectbox("Language", language_values)
        call_status_filter = f2.selectbox("Call status", call_status_values)
        qualification_filter = f3.selectbox("Qualification", qualification_values)

        filtered_sessions = filter_sessions(
            sessions,
            search_text,
            language_filter,
            call_status_filter,
            qualification_filter,
        )
        st.caption(f"{len(filtered_sessions)} / {len(sessions)} sessions shown")

        df = flatten_sessions_for_table(filtered_sessions)
        st.dataframe(df, use_container_width=True, hide_index=True)

    with right:
        st.subheader("Quick analytics")
        if sessions:
            call_status_df = count_by_key(sessions, "call_status")
            qualification_df = count_by_key(sessions, "qualification_status")

            st.markdown("**Call status mix**")
            if not call_status_df.empty:
                st.bar_chart(call_status_df.set_index("label"))

            st.markdown("**Qualification mix**")
            if not qualification_df.empty:
                st.bar_chart(qualification_df.set_index("label"))
        else:
            st.info("No session analytics yet.")

        st.divider()
        st.markdown("**Platform disclosure**")
        if disclosure_error:
            st.error(disclosure_error)
        else:
            st.json(disclosure)

with launch_tab:
    st.subheader("Create live outbound call")

    with st.form("launch_call_form"):
        customer_number = st.text_input("Customer number", placeholder="+91XXXXXXXXXX")
        customer_name = st.text_input("Customer name (optional)", placeholder="Rajendra")
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
                session_id = created.get("session_id")
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
                st.success("Outbound call created successfully.")
                st.json(launched)

                call_id = launched.get("call_id")
                if call_id:
                    st.info(f"Call ID: {call_id}")

with sessions_tab:
    st.subheader("Session explorer")

    sessions_data, sessions_error = safe_get_json(f"{base_url}/api/v1/conversation/sessions")
    if sessions_error:
        st.error(f"Could not load sessions: {sessions_error}")
    else:
        sessions = sessions_data or []
        session_map = {s["session_id"]: s for s in sessions if "session_id" in s}

        if not session_map:
            st.info("No sessions yet.")
        else:
            selected_session_id = st.selectbox(
                "Choose session",
                options=list(session_map.keys()),
            )

            session_detail, session_detail_error = safe_get_json(
                f"{base_url}/api/v1/conversation/sessions/{selected_session_id}"
            )

            if session_detail_error:
                st.error(f"Could not load session detail: {session_detail_error}")
            else:
                session = session_detail.get("session", {})
                top1, top2, top3, top4 = st.columns(4)
                top1.metric("Language", session.get("language", "-"))
                top2.metric("State", session.get("state", "-"))
                top3.metric("Qualification", session.get("qualification_status", "-"))
                top4.metric("Call status", session.get("call_status", "-"))

                st.divider()
                left, right = st.columns([1, 1])

                with left:
                    st.markdown("**Session object**")
                    st.json(session)

                with right:
                    st.markdown("**Captured slots**")
                    st.json(session.get("slots", {}))
                    st.markdown("**Slot confidence**")
                    st.json(session.get("slot_confidence", {}))

                st.divider()
                st.markdown("**Transcript**")
                render_transcript(session)

                st.divider()
                linked_artifact = latest_artifact_for_call(artifacts_root, session.get("external_call_id"))
                if linked_artifact:
                    st.success(f"Artifact folder found: {linked_artifact.name}")
                    st.json(artifact_summary(linked_artifact))
                else:
                    st.info("No local artifact folder matched to this session's external call ID yet.")

with review_tab:
    st.subheader("Call review and QA")

    sessions_data, sessions_error = safe_get_json(f"{base_url}/api/v1/conversation/sessions")
    if sessions_error:
        st.error(f"Could not load sessions for review: {sessions_error}")
    else:
        sessions = sessions_data or []
        session_map = {s["session_id"]: s for s in sessions if "session_id" in s}

        if not session_map:
            st.info("No sessions available for review yet.")
        else:
            review_session_id = st.selectbox(
                "Choose session to review",
                options=list(session_map.keys()),
                key="review_session_select",
            )

            session_detail, session_detail_error = safe_get_json(
                f"{base_url}/api/v1/conversation/sessions/{review_session_id}"
            )

            if session_detail_error:
                st.error(f"Could not load session detail: {session_detail_error}")
            else:
                session = session_detail.get("session", {})
                linked_artifact = latest_artifact_for_call(artifacts_root, session.get("external_call_id"))
                previous_review = latest_review_for_session(artifacts_root, review_session_id) or {}

                top1, top2, top3, top4 = st.columns(4)
                top1.metric("Language", session.get("language", "-"))
                top2.metric("Call status", session.get("call_status", "-"))
                top3.metric("Qualification", session.get("qualification_status", "-"))
                top4.metric("State", session.get("state", "-"))

                left, right = st.columns([1.2, 1])

                with left:
                    st.markdown("**Captured slots**")
                    st.json(session.get("slots", {}))

                    st.markdown("**Transcript**")
                    render_transcript(session)

                with right:
                    st.markdown("**Linked artifact summary**")
                    if linked_artifact:
                        st.success(f"Artifact found: {linked_artifact.name}")
                        st.json(artifact_summary(linked_artifact))

                        audio_files = find_audio_files(linked_artifact)
                        if audio_files:
                            st.markdown("**Audio replay**")
                            audio_file = audio_files[0]
                            st.audio(str(audio_file), format=guess_audio_format(audio_file))
                    else:
                        st.info("No linked artifact folder found for this session yet.")

                st.divider()
                st.markdown("**Reviewer form**")

                verdict_options = [
                    "approved_for_demo",
                    "qualified",
                    "callback_needed",
                    "human_handoff",
                    "not_interested",
                    "needs_retry",
                    "bad_call",
                ]
                saved_verdict = previous_review.get("verdict", "needs_retry")
                verdict_index = verdict_options.index(saved_verdict) if saved_verdict in verdict_options else 5

                with st.form("review_form"):
                    reviewer_name = st.text_input(
                        "Reviewer name",
                        value=previous_review.get("reviewer_name", ""),
                    )

                    verdict = st.selectbox(
                        "Final verdict",
                        options=verdict_options,
                        index=verdict_index,
                    )

                    issues = st.multiselect(
                        "Observed issues",
                        options=[
                            "language_switch_issue",
                            "voice_quality_issue",
                            "pronunciation_issue",
                            "interruption_issue",
                            "looping_issue",
                            "objection_handling_issue",
                            "qualification_logic_issue",
                            "no_recording_found",
                            "no_transcript_found",
                        ],
                        default=previous_review.get("issues", []),
                    )

                    notes = st.text_area(
                        "Reviewer notes",
                        value=previous_review.get("notes", ""),
                        height=150,
                    )

                    submitted_review = st.form_submit_button("Save review", use_container_width=True)

                if submitted_review:
                    review = {
                        "reviewed_at": datetime.now(timezone.utc).isoformat(),
                        "session_id": review_session_id,
                        "external_call_id": session.get("external_call_id"),
                        "customer_number": session.get("customer_number"),
                        "language": session.get("language"),
                        "call_status": session.get("call_status"),
                        "qualification_status": session.get("qualification_status"),
                        "verdict": verdict,
                        "issues": issues,
                        "reviewer_name": reviewer_name.strip(),
                        "notes": notes.strip(),
                    }
                    save_review_entry(artifacts_root, review)
                    st.success("Review saved locally.")

    st.divider()
    st.markdown("**Reviewed calls export**")

    review_df = reviews_as_dataframe(artifacts_root)
    st.dataframe(review_df, use_container_width=True, hide_index=True)

    if not review_df.empty:
        csv_data = review_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download reviews CSV",
            data=csv_data,
            file_name="call_reviews.csv",
            mime="text/csv",
            use_container_width=True,
        )

with artifacts_tab:
    st.subheader("Saved call artifacts")

    call_dirs = get_call_artifact_dirs(artifacts_root)
    if not call_dirs:
        st.info("No saved call artifacts found yet.")
    else:
        artifact_search = st.text_input("Filter artifact folders by call ID")
        visible_dirs = (
            [p for p in call_dirs if artifact_search.strip().lower() in p.name.lower()]
            if artifact_search.strip()
            else call_dirs
        )

        if not visible_dirs:
            st.info("No artifact folders match the filter.")
        else:
            selected_dir = st.selectbox(
                "Choose call artifact folder",
                options=visible_dirs,
                format_func=lambda p: p.name,
            )

            st.caption(f"Folder: {selected_dir}")
            artifact_json = selected_dir / "artifact.json"
            transcript_txt = selected_dir / "transcript.txt"
            messages_json = selected_dir / "messages.json"

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
                    st.text_area("Transcript", transcript_text, height=250)
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

with providers_tab:
    st.subheader("Provider inspection")

    disclosure, disclosure_error = safe_get_json(f"{base_url}/api/v1/providers/disclosure")
    payload, payload_error = safe_post_json(f"{base_url}/api/v1/providers/vapi/assistant-payload", {})

    left, right = st.columns(2)

    with left:
        st.markdown("**Platform disclosure**")
        if disclosure_error:
            st.error(disclosure_error)
        else:
            st.json(disclosure)

    with right:
        st.markdown("**Current Vapi assistant payload**")
        if payload_error:
            st.error(payload_error)
        else:
            st.json(payload)