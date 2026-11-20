import streamlit as st
from core.config import ALLOWED_COUNTRIES
from core.db import get_db
from core.retrieval import fetch_required_documents
from core.compliance import run_compliance_check
from core.chatbot import ask


def page():
    st.title("✅ Visa Document Compliance Check")
    user = st.session_state.user

    country = st.selectbox("Country", ALLOWED_COUNTRIES)

    db = get_db()
    rows = (db.table("visa_rules").select("route_group")
            .eq("country", country).eq("is_active", True).execute().data or [])
    route_groups = sorted({r["route_group"] for r in rows})
    if not route_groups:
        st.warning("No routes loaded yet. Ask a parser to ingest rules first.")
        _chat_sidebar(user)
        return

    route_group = st.selectbox("Visa category", route_groups)

    subs = (db.table("visa_rules").select("sub_path")
            .eq("country", country).eq("route_group", route_group)
            .eq("is_active", True).execute().data or [])
    sub_paths = sorted({s["sub_path"] for s in subs if s["sub_path"]})
    sub_path = None
    if sub_paths:
        pick = st.selectbox("Sub-path (optional)", ["(none)"] + sub_paths)
        if pick != "(none)":
            sub_path = pick

    # Clear stale upload state when the selection changes
    route_key = f"{country}|{route_group}|{sub_path}"
    if st.session_state.get("current_route_key") != route_key:
        st.session_state.current_route_key = route_key
        st.session_state.uploaded_files = {}
        st.session_state.last_check = None

    reqs = fetch_required_documents(country, route_group, sub_path)
    if not reqs:
        st.info("No required documents listed for this route yet.")
        _chat_sidebar(user)
        return

    st.caption(
        "Files are sent raw to Gemini and discarded after the check. "
        "VoyaTrace stores only filename, size, and hash — never document content."
    )
    
    uploads = st.session_state.setdefault("uploaded_files", {})

    # Split the required docs into three groups based on status
    mandatory_docs = [r for r in reqs if r.get("requirement_status", "Mandatory") == "Mandatory"]
    conditional_docs = [r for r in reqs if r.get("requirement_status") == "Conditional"]
    supporting_docs = [r for r in reqs if r.get("requirement_status") == "Supporting"]

    def render_uploaders(doc_list, is_optional=False):
        for r in doc_list:
            key = r["doc_type"]
            # Add asterisk only if it's mandatory
            asterisk = " *" if not is_optional else " (Optional)"
            label = f"{r['doc_label']}{asterisk}"
            
            f = st.file_uploader(
                label, key=f"upload_{route_key}_{key}",
                type=["pdf", "txt", "docx", "jpg", "jpeg", "png"],
                accept_multiple_files=False,
            )
            
            # Show the trigger condition for conditional docs
            if r.get("trigger_condition"):
                st.caption(f"⚠️ **Condition:** {r['trigger_condition']}")
                
            if f is not None:
                uploads[key] = {
                    "doc_type": key,
                    "filename": f.name,
                    "mime_type": f.type or "application/octet-stream",
                    "bytes": f.read(),
                }

    # --- RENDER UI SECTIONS ---
    if mandatory_docs:
        st.subheader("Mandatory Documents")
        render_uploaders(mandatory_docs)

    if conditional_docs:
        st.subheader("Conditional Documents")
        st.info("You only need to upload these if the condition applies to you.")
        render_uploaders(conditional_docs)

    if supporting_docs:
        with st.expander("➕ Add Optional / Supporting Documents"):
            render_uploaders(supporting_docs, is_optional=True)

    st.divider()

    if st.button("Run compliance check", type="primary"):
        if not uploads:
            st.error("Upload at least one document.")
        else:
            with st.spinner("Checking documents against official rules…"):
                out = run_compliance_check(
                    user["id"], country, route_group, sub_path,
                    list(uploads.values()),
                )
                if out.get("error"):
                    st.error(out["error"])
                else:
                    st.session_state.last_check = out
                    st.session_state.last_route = (country, route_group, sub_path)

    _chat_sidebar(user)
    _render_result(st.session_state.get("last_check"))


def _render_result(out):
    if not out:
        return
    result = out.get("result", {})
    st.divider()
    st.subheader("Result")
    st.info(result.get("summary", "No summary."))
    for v in result.get("verdicts", []):
        status = v.get("status", "UNKNOWN")
        icon = {"PASS": "✅", "FAIL": "❌",
                "MISSING": "⚠️", "UNKNOWN": "❔"}.get(status, "•")
        with st.expander(f"{icon} {v.get('rule_title','(rule)')} — {status}"):
            st.write(f"**Document:** {v.get('doc_type','—')}")
            if v.get("gap_value"):
                st.write(f"**Gap:** {v['gap_value']}")
            st.write(v.get("notes", ""))
    if result.get("next_steps"):
        st.markdown("**Next steps**")
        for s in result["next_steps"]:
            st.markdown(f"- {s}")


def _chat_sidebar(user):
    with st.sidebar:
        st.divider()
        st.markdown("### 💬 Ask VoyaTrace")
        st.caption("Answers only from official rules + your last check. Not a visa guarantee.")
        hist = st.session_state.setdefault("chat_history", [])
        for msg in hist:
            st.chat_message(msg["role"]).write(msg["content"])
        with st.form("chat_form", clear_on_submit=True):
            q = st.text_input("Ask about your documents…",
                              label_visibility="collapsed",
                              placeholder="e.g. Why did my financial check fail?")
            sent = st.form_submit_button("Send")
        if sent and q:
            hist.append({"role": "user", "content": q})
            route = (st.session_state.get("last_route")
                     or (ALLOWED_COUNTRIES[0], None, None))
            summary = ((st.session_state.get("last_check") or {})
                       .get("result", {}).get("summary"))
            with st.spinner("Searching rules…"):
                try:
                    answer = ask(user, q, route[0], route[1], summary)
                except Exception as e:
                    answer = f"Chat error: {e}"
            hist.append({"role": "assistant", "content": answer})
            st.rerun()
