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
    col1, col2 = st.columns(2)
    with col1:
        country = st.selectbox("Country", ALLOWED_COUNTRIES)
    with col2:
        route_group = st.text_input("Route group (e.g. EU Blue Card)", key="active_route")

    if not route_group:
        st.info("Please type a Route Group above and press Enter to load existing data.")
        return

    # --- SUB-PATH DROPDOWN (Fixes Bug 2) ---
    subs_query = (db.table("visa_rules").select("sub_path")
                  .eq("country", country).eq("route_group", route_group)
                  .not_.is_("sub_path", "null").execute().data)
    existing_subs = sorted(list(set([s["sub_path"] for s in subs_query if s["sub_path"]])))
    sub_options = ["(None)"] + existing_subs + ["➕ Add New Sub-path"]
    
    sub_choice = st.selectbox("Sub-path", sub_options)
    if sub_choice == "➕ Add New Sub-path":
        sub_path = st.text_input("Enter new Sub-path name")
        if not sub_path:
            st.warning("Please type the new sub-path name.")
            return
    elif sub_choice == "(None)":
        sub_path = None
    else:
        sub_path = sub_choice

    st.divider()

    # --- SECTION 1: STRUCTURED THRESHOLDS (Fixes Bug 4) ---
    st.subheader("1. Structured Thresholds (Strict Math)")
    st.caption("Add hard numbers here so the AI doesn't have to guess from text.")
    
    # Load existing thresholds
    t_query = db.table("route_thresholds").select("*").eq("country", country).eq("route_group", route_group)
    if sub_path:
        t_query = t_query.eq("sub_path", sub_path)
    else:
        t_query = t_query.is_("sub_path", "null")
    thresholds = t_query.execute().data
    
    thresh_opts = {f"[{t['id']}] {t['description']} ({t['condition']})": t for t in thresholds}
    sel_thresh = st.selectbox("Select a threshold to Edit, or Add New:", ["➕ Add New Threshold"] + list(thresh_opts.keys()))
    
    # Default form values
    t_val = {"id": None, "field": "salary", "amount": 0.0, "condition": "", "description": ""}
    if sel_thresh != "➕ Add New Threshold":
        t_val = thresh_opts[sel_thresh]

    with st.form("threshold_form", clear_on_submit=(sel_thresh == "➕ Add New Threshold")):
        t_col1, t_col2, t_col3, t_col4 = st.columns(4)
        
        field_options = ["salary", "age", "experience_years", "funds"]
        field_idx = field_options.index(t_val["field"]) if t_val["field"] in field_options else 0
        
        t_field = t_col1.selectbox("Field", field_options, index=field_idx)
        t_amount = t_col2.number_input("Amount / Number", value=float(t_val["amount"]), step=1000.0)
        t_condition = t_col3.text_input("Condition (e.g. age >= 45)", value=t_val["condition"])
        t_desc = t_col4.text_input("Description (e.g. Salary for 45+)", value=t_val["description"])
        
        if st.form_submit_button("Save Threshold"):
            if not t_desc:
                st.error("Description is required.")
            else:
                payload = {
                    "country": country, "route_group": route_group, "sub_path": sub_path,
                    "field": t_field, "amount": t_amount, "condition": t_condition, "description": t_desc
                }
                if t_val["id"]:
                    # Update existing
                    db.table("route_thresholds").update(payload).eq("id", t_val["id"]).execute()
                    st.success("Threshold updated.")
                else:
                    # Insert new
                    db.table("route_thresholds").insert(payload).execute()
                    st.success("Threshold added.")
                st.rerun()

    # Delete option outside the form
    if t_val["id"]:
        if st.button(f"🗑️ Delete Threshold: {sel_thresh}"):
            db.table("route_thresholds").delete().eq("id", t_val["id"]).execute()
            st.rerun()

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
                        user["id"], country, route_group, sub_path, 
                        section_title, text, 2026, None, source_type, verified_at
                    )
                mirror("visa_rules.json", {
                    "country": country, "route_group": route_group, "sub_path": sub_path,
                    "section_title": section_title, "chunks": n, "source_type": source_type
                })
                log_event(user["id"], "parser_ingest", f"{country}/{route_group} ({n} chunks)")
                st.success(f"Ingested {n} chunks. (Previous rules for this section are now deactivated).")
                st.rerun()

    # Load active rules
    rules = (db.table("visa_rules")
             .select("id, chunk_index, section_title, source_type, verified_at")
             .eq("country", country).eq("route_group", route_group)
             .eq("is_active", True))
    if sub_path:
        rules = rules.eq("sub_path", sub_path)
    else:
        rules = rules.is_("sub_path", "null")
    rules = rules.order("chunk_index").execute().data or []
    
    if rules:
        with st.expander(f"📄 View Active Ingested Rules ({len(rules)} chunks)", expanded=False):
            st.dataframe(rules, use_container_width=True)
            
            st.write("**Manage / Delete Rules**")
            col_del1, col_del2 = st.columns(2)
            
            with col_del1:
                del_id = st.number_input("Delete by Rule ID (see table above)", min_value=0, step=1, value=0)
                if st.button("Delete Rule ID"):
                    if del_id > 0:
                        db.table("visa_rules").delete().eq("id", int(del_id)).execute()
                        st.success(f"Deleted chunk {del_id}.")
                        st.rerun()
            
            with col_del2:
                st.write("Or completely wipe this route:")
                if st.button("🗑️ Delete ALL Rules for this Route", type="primary"):
                    q = db.table("visa_rules").delete().eq("country", country).eq("route_group", route_group).eq("is_active", True)
                    if sub_path:
                        q = q.eq("sub_path", sub_path)
                    else:
                        q = q.is_("sub_path", "null")
                    q.execute()
                    st.success("All active rules deleted.")
                    st.rerun()
    else:
        st.caption("No active rules ingested yet.")

    st.divider()

    # --- SECTION 3: DOCUMENT SLOTS (Fixes Bug 3) ---
    st.subheader("3. Required Document Slots")
    st.caption("Tell the AI exactly how to check each document.")
    
    existing_docs = fetch_required_documents(country, route_group, sub_path)
    doc_options = ["➕ Add New Document Slot"] + [d['doc_type'] for d in existing_docs]
    
    selected_doc = st.selectbox("Select a document to Edit, or Add New:", doc_options)

    # Default values
    d_val = {
        "doc_type": "", "doc_label": "", "requirement_status": "Mandatory", 
        "trigger_condition": "", "ai_check_instruction": "", "display_order": 99
    }
    
    if selected_doc != "➕ Add New Document Slot":
        d_val = next(d for d in existing_docs if d['doc_type'] == selected_doc)

    with st.form("doc_form", clear_on_submit=(selected_doc == "➕ Add New Document Slot")):
        d_col1, d_col2, d_col3, d_col4 = st.columns(4)
        
        # Disable doc_type if editing (it acts as the primary key)
        doc_type = d_col1.text_input("doc_type (slug)", value=d_val["doc_type"], disabled=(selected_doc != "➕ Add New Document Slot"))
        doc_label = d_col2.text_input("Label shown to user", value=d_val["doc_label"], placeholder="Recent Bank Statement")
        
        status_options = ["Mandatory", "Conditional", "Supporting"]
        status_idx = status_options.index(d_val["requirement_status"]) if d_val["requirement_status"] in status_options else 0
        req_status = d_col3.selectbox("Requirement Status", status_options, index=status_idx)
        
        # New Display Order field
        display_order = d_col4.number_input("Display Order (1 = top)", min_value=1, max_value=999, value=int(d_val["display_order"]))
        
        trigger_cond = st.text_input("Trigger Condition (Only if status is 'Conditional')", value=d_val["trigger_condition"], placeholder="e.g. Only if applicant is over 45")
        ai_prompt = st.text_area("AI Check Instruction", value=d_val["ai_check_instruction"], placeholder="Extract the final balance. Check if it is >= 11,904 EUR.")
        
        if st.form_submit_button("Save Document Slot"):
            if not doc_type or not doc_label:
                st.error("doc_type and Label are required.")
            else:
                # Delete then insert handles both Create and Update cleanly
                _delete_required_doc(db, country, route_group, sub_path, doc_type)
                db.table("required_documents").insert({
                    "country": country, "route_group": route_group, "sub_path": sub_path,
                    "doc_type": doc_type, "doc_label": doc_label, 
                    "requirement_status": req_status, "trigger_condition": trigger_cond or None,
                    "ai_check_instruction": ai_prompt or None,
                    "display_order": int(display_order)
                }).execute()
                log_event(user["id"], "parser_upsert_doc", f"{country}/{route_group}/{doc_type}")
                st.success(f"Saved document slot '{doc_type}'.")
                st.rerun()

    # Show all existing docs and delete option
    if existing_docs:
        # Sort the display table by the new display_order
        existing_docs.sort(key=lambda x: x.get('display_order', 99))
        st.write("**Existing Document Slots (Ordered by Display Order):**")
        
        # Only show relevant columns in the table
        table_data = [{
            "Order": d.get("display_order"), "doc_type": d["doc_type"], 
            "Label": d["doc_label"], "Status": d.get("requirement_status")
        } for d in existing_docs]
        st.dataframe(table_data, use_container_width=True)
        
        del_doc = st.selectbox("Select a document to delete", ["(Select to delete)"] + [d['doc_type'] for d in existing_docs])
        if del_doc != "(Select to delete)":
            if st.button(f"🗑️ Delete Document: {del_doc}"):
                _delete_required_doc(db, country, route_group, sub_path, del_doc)
                st.rerun()
