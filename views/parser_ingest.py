import streamlit as st
from datetime import date
from core.config import ALLOWED_COUNTRIES
from core.db import get_db
from core.parser_ingest import ingest_route
from core.retrieval import fetch_required_documents
from core.offline_mirror import mirror
from core.system_events import log_event


def _delete_required_doc(db, country, route_group, sub_path, doc_type):
    q = (db.table("required_documents").delete()
         .eq("country", country)
         .eq("route_group", route_group)
         .eq("doc_type", doc_type))
    if sub_path:
        q = q.eq("sub_path", sub_path)
    else:
        q = q.is_("sub_path", "null")
    q.execute()


def page():
    st.title("📥 Ingest / Update Embassy Rules")
    user = st.session_state.user
    if user["role"] not in ("parser", "admin"):
        st.error("Parsers and admins only.")
        return

    db = get_db()

    # --- ROUTE SELECTOR ---
    col1, col2, col3 = st.columns(3)
    with col1:
        country = st.selectbox("Country", ALLOWED_COUNTRIES)
    with col2:
        route_group = st.text_input("Route group (e.g. EU Blue Card)")
    with col3:
        sub_path = st.text_input("Sub-path (optional)")

    if not route_group:
        st.info("Please enter a Route group above to start.")
        return

    st.divider()

    # --- SECTION 1: STRUCTURED THRESHOLDS (The Math) ---
    st.subheader("1. Structured Thresholds (Strict Math)")
    st.caption("Add hard numbers here so the AI doesn't have to guess from text. E.g., Age >= 45 requires 55,770 EUR.")
    
    with st.form("threshold_form", clear_on_submit=True):
        t_col1, t_col2, t_col3, t_col4 = st.columns(4)
        t_field = t_col1.selectbox("Field", ["salary", "age", "experience_years", "funds"])
        t_amount = t_col2.number_input("Amount / Number", value=0.0, step=1000.0)
        t_condition = t_col3.text_input("Condition (e.g. age >= 45)")
        t_desc = t_col4.text_input("Description (e.g. Salary for 45+)")
        
        if st.form_submit_button("Add Threshold"):
            if t_desc:
                db.table("route_thresholds").insert({
                    "country": country, "route_group": route_group, "sub_path": sub_path or None,
                    "field": t_field, "amount": t_amount, "condition": t_condition, "description": t_desc
                }).execute()
                st.success("Threshold added.")
                st.rerun()
            else:
                st.error("Description is required.")

    # Show current thresholds
    t_query = db.table("route_thresholds").select("*").eq("country", country).eq("route_group", route_group)
    if sub_path:
        t_query = t_query.eq("sub_path", sub_path)
    else:
        t_query = t_query.is_("sub_path", "null")
    
    thresholds = t_query.execute().data
    if thresholds:
        st.dataframe(thresholds, use_container_width=True)
        del_t_id = st.number_input("Delete Threshold ID (0 = none)", min_value=0, step=1, value=0, key="del_t")
        if del_t_id and st.button("Delete Threshold"):
            db.table("route_thresholds").delete().eq("id", int(del_t_id)).execute()
            st.rerun()
    else:
        st.caption("No thresholds defined yet.")

    st.divider()

    # --- SECTION 2: RULES TEXT & SOURCE TRACKING ---
    st.subheader("2. Official Rules Text")
    with st.form("rules_form"):
        r_col1, r_col2, r_col3 = st.columns(3)
        section_title = r_col1.text_input("Section title (e.g. '2026 Salary Rules')")
        source_type = r_col2.selectbox("Source Type", ["Embassy Dhaka", "Federal Law", "Local Authority", "Make it in Germany"])
        verified_at = r_col3.date_input("Last Verified Date", value=date.today())
        
        text = st.text_area("Rule Text (chunked + embedded with Gemini)", height=200)
        
        if st.form_submit_button("Ingest Rules"):
            if not text.strip():
                st.error("Rule text is required.")
            else:
                with st.spinner("Chunking + embedding..."):
                    n = ingest_route(
                        user["id"], country, route_group, sub_path or None, 
                        section_title, text, 2026, None, source_type, verified_at
                    )
                mirror("visa_rules.json", {
                    "country": country, "route_group": route_group, "sub_path": sub_path or None,
                    "section_title": section_title, "chunks": n, "source_type": source_type
                })
                log_event(user["id"], "parser_ingest", f"{country}/{route_group} ({n} chunks)")
                st.success(f"Ingested {n} chunks.")
                st.rerun()

    # Show active rules
    rules = (db.table("visa_rules")
             .select("id, chunk_index, section_title, source_type, verified_at, is_active")
             .eq("country", country).eq("route_group", route_group)
             .eq("is_active", True).order("chunk_index").execute().data or [])
    if rules:
        st.dataframe(rules, use_container_width=True)

    st.divider()

    # --- SECTION 3: DOCUMENT SLOTS ---
    st.subheader("3. Required Document Slots")
    st.caption("Tell the AI exactly how to check each document.")
    
    with st.form("doc_form", clear_on_submit=True):
        d_col1, d_col2, d_col3 = st.columns(3)
        doc_type = d_col1.text_input("doc_type (slug)", placeholder="bank_statement")
        doc_label = d_col2.text_input("Label shown to user", placeholder="Recent Bank Statement")
        req_status = d_col3.selectbox("Requirement Status", ["Mandatory", "Conditional", "Supporting"])
        
        trigger_cond = ""
        if req_status == "Conditional":
            trigger_cond = st.text_input("Trigger Condition", placeholder="e.g. Only if applying under 45 age rule")
            
        ai_prompt = st.text_area("AI Check Instruction", placeholder="Extract the final balance. Check if it is >= 11,904 EUR.")
        
        if st.form_submit_button("Upsert Document Slot"):
            if not doc_type or not doc_label:
                st.error("doc_type and Label are required.")
            else:
                _delete_required_doc(db, country, route_group, sub_path or None, doc_type)
                db.table("required_documents").insert({
                    "country": country, "route_group": route_group, "sub_path": sub_path or None,
                    "doc_type": doc_type, "doc_label": doc_label, 
                    "requirement_status": req_status, "trigger_condition": trigger_cond or None,
                    "ai_check_instruction": ai_prompt or None,
                    "display_order": 99
                }).execute()
                log_event(user["id"], "parser_upsert_doc", f"{country}/{route_group}/{doc_type}")
                st.success(f"Upserted document slot '{doc_type}'.")
                st.rerun()

    # Show current docs
    existing = fetch_required_documents(country, route_group, sub_path or None)
    if existing:
        st.dataframe(existing, use_container_width=True)
        del_doc_id = st.number_input("Delete Document ID (0 = none)", min_value=0, step=1, value=0, key="del_d")
        if del_doc_id and st.button("Delete Document Slot"):
            db.table("required_documents").delete().eq("id", int(del_doc_id)).execute()
            st.rerun()
