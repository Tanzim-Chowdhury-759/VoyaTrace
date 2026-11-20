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
        # We use a text input here, but Streamlit automatically reruns the app
        # and loads everything below as soon as you press Enter.
        route_group = st.text_input("Route group (e.g. EU Blue Card)", key="active_route")
    with col3:
        sub_path = st.text_input("Sub-path (optional)")

    if not route_group:
        st.info("Please type a Route Group above and press Enter to load existing data.")
        return

    st.divider()

    # --- SECTION 1: STRUCTURED THRESHOLDS ---
    st.subheader("1. Structured Thresholds (Strict Math)")
    st.caption("Add hard numbers here so the AI doesn't have to guess from text.")
    
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

    # Load existing thresholds
    t_query = db.table("route_thresholds").select("*").eq("country", country).eq("route_group", route_group)
    if sub_path:
        t_query = t_query.eq("sub_path", sub_path)
    else:
        t_query = t_query.is_("sub_path", "null")
    
    thresholds = t_query.execute().data
    if thresholds:
        # Create a friendly format for the selectbox
        thresh_dict = {f"[{t['id']}] {t['description']} ({t['condition']})": t['id'] for t in thresholds}
        st.write("**Existing Thresholds:**")
        selected_thresh = st.selectbox("Select a threshold to delete", ["(Select to delete)"] + list(thresh_dict.keys()))
        
        if selected_thresh != "(Select to delete)":
            if st.button(f"🗑️ Delete Threshold: {selected_thresh}"):
                db.table("route_thresholds").delete().eq("id", thresh_dict[selected_thresh]).execute()
                st.rerun()
    else:
        st.caption("No thresholds defined yet for this route.")

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
                st.success(f"Ingested {n} chunks. (Previous rules for this section are now deactivated).")
                st.rerun()

    # Load active rules
    rules = (db.table("visa_rules")
             .select("id, chunk_index, section_title, source_type, verified_at")
             .eq("country", country).eq("route_group", route_group)
             .eq("is_active", True).order("chunk_index").execute().data or [])
    if rules:
        with st.expander(f"📄 View Active Ingested Rules ({len(rules)} chunks)"):
            st.dataframe(rules, use_container_width=True)
            st.caption("Note: To update a rule, simply paste the new text in the form above and click 'Ingest Rules'. The old text is automatically deactivated.")
    else:
        st.caption("No active rules ingested yet.")

    st.divider()

    # --- SECTION 3: DOCUMENT SLOTS ---
    st.subheader("3. Required Document Slots")
    st.caption("Tell the AI exactly how to check each document.")
    
    # Load existing docs to populate the edit dropdown
    existing_docs = fetch_required_documents(country, route_group, sub_path or None)
    doc_options = ["➕ Add New Document Slot"] + [d['doc_type'] for d in existing_docs]
    
    selected_doc = st.selectbox("Select a document to Edit, or Add New:", doc_options)

    # Default form values
    d_type, d_label, d_status, d_cond, d_prompt = "", "", "Mandatory", "", ""

    # If editing an existing doc, populate the form fields
    if selected_doc != "➕ Add New Document Slot":
        for d in existing_docs:
            if d['doc_type'] == selected_doc:
                d_type = d['doc_type']
                d_label = d['doc_label']
                d_status = d.get('requirement_status', 'Mandatory')
                d_cond = d.get('trigger_condition') or ""
                d_prompt = d.get('ai_check_instruction') or ""
                break

    with st.form("doc_form"):
        d_col1, d_col2, d_col3 = st.columns(3)
        # Disable changing the doc_type if we are editing an existing one
        doc_type = d_col1.text_input("doc_type (slug)", value=d_type, disabled=(selected_doc != "➕ Add New Document Slot"))
        doc_label = d_col2.text_input("Label shown to user", value=d_label, placeholder="Recent Bank Statement")
        
        # Set the index of the selectbox based on the existing status
        status_options = ["Mandatory", "Conditional", "Supporting"]
        status_index = status_options.index(d_status) if d_status in status_options else 0
        req_status = d_col3.selectbox("Requirement Status", status_options, index=status_index)
        
        trigger_cond = st.text_input("Trigger Condition (Only if status is 'Conditional')", value=d_cond, placeholder="e.g. Only if applicant is over 45")
        ai_prompt = st.text_area("AI Check Instruction", value=d_prompt, placeholder="Extract the final balance. Check if it is >= 11,904 EUR.")
        
        if st.form_submit_button("Save Document Slot"):
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
                st.success(f"Saved document slot '{doc_type}'.")
                st.rerun()

    # Show all existing docs and delete option
    if existing_docs:
        st.write("**Existing Document Slots:**")
        st.dataframe(existing_docs, use_container_width=True)
        
        del_doc = st.selectbox("Select a document to delete", ["(Select to delete)"] + [d['doc_type'] for d in existing_docs])
        if del_doc != "(Select to delete)":
            if st.button(f"🗑️ Delete Document: {del_doc}"):
                _delete_required_doc(db, country, route_group, sub_path or None, del_doc)
                st.rerun()
