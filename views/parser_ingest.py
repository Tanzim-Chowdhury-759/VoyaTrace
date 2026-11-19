import streamlit as st
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

    country = st.selectbox("Country", ALLOWED_COUNTRIES)
    col1, col2 = st.columns(2)
    with col1:
        route_group = st.text_input("Route group (e.g. EU Blue Card, Student Visa)")
    with col2:
        sub_path = st.text_input("Sub-path (optional, e.g. 'IT Blue Card without degree')")
    section_title = st.text_input("Section title (e.g. '2026 salary thresholds')")
    effective_year = st.number_input("Effective year", min_value=2000, max_value=2100, value=2026)
    source_url = st.text_input("Source URL (optional)")
    text = st.text_area(
        "Rule text (chunked + embedded with gemini-embedding-001)", height=300)

    if st.button("Ingest rules", type="primary"):
        if not route_group or not text.strip():
            st.error("Route group and rule text are required.")
        else:
            with st.spinner("Chunking + embedding…"):
                n = ingest_route(
                    user["id"], country, route_group,
                    sub_path or None, section_title, text,
                    int(effective_year), source_url or None,
                )
            mirror("visa_rules.json", {
                "country": country,
                "route_group": route_group,
                "sub_path": sub_path or None,
                "section_title": section_title,
                "chunks": n,
                "effective_year": int(effective_year),
                "source_url": source_url,
                "created_by": user["username"],
            })
            log_event(user["id"], "parser_ingest",
                      f"{country}/{route_group} ({n} chunks)")
            st.success(f"Ingested {n} chunks for {route_group}.")

    # ---------------- Required documents management ----------------
    st.divider()
    st.subheader("Required document slots for this route")
    st.caption("These are the upload fields the user sees on the Check page.")

    db = get_db()
    existing = fetch_required_documents(country, route_group, sub_path or None)

    if existing:
        table_rows = [{
            "id": d["id"],
            "doc_type": d["doc_type"],
            "label": d["doc_label"],
            "required": d["is_required"],
            "evidence": d.get("evidence_label") or "",
            "order": d.get("display_order", 0),
        } for d in existing]
        st.dataframe(table_rows, use_container_width=True)

        del_id = st.number_input(
            "Delete document ID (0 = no delete)",
            min_value=0, step=1, value=0, key="del_doc_id",
        )
        if del_id and st.button("Delete this document", key="del_doc_btn"):
            db.table("required_documents").delete().eq("id", int(del_id)).execute()
            log_event(user["id"], "parser_delete_doc", f"id={del_id}")
            st.success(f"Deleted document {del_id}.")
            st.rerun()
    else:
        st.caption("No document slots defined yet for this route.")

    st.markdown("**Add or update a document slot**")
    c1, c2, c3, c4 = st.columns(4)
    new_dt = c1.text_input("doc_type (slug)", key="new_dt",
                           placeholder="bank_statement")
    new_label = c2.text_input("Label shown to user", key="new_lbl",
                              placeholder="Recent bank statement")
    new_req = c3.checkbox("Required", value=True, key="new_req")
    new_ev = c4.selectbox(
        "Evidence label", ["", "D", "F", "C", "V"], key="new_ev",
        help="D=Dhaka-explicit, F=Federal, C=Conditional, V=Verify",
    )
    new_order = st.number_input("Display order", min_value=0, step=1,
                                value=99, key="new_ord")

    if st.button("Upsert document slot", key="upsert_doc_btn"):
        if not new_dt or not new_label:
            st.error("doc_type and label are required.")
        else:
            _delete_required_doc(db, country, route_group, sub_path or None, new_dt)
            db.table("required_documents").insert({
                "country": country,
                "route_group": route_group,
                "sub_path": sub_path or None,
                "doc_type": new_dt,
                "doc_label": new_label,
                "is_required": new_req,
                "evidence_label": new_ev or None,
                "display_order": int(new_order),
            }).execute()
            log_event(user["id"], "parser_upsert_doc",
                      f"{country}/{route_group}/{new_dt}")
            st.success(f"Upserted document slot '{new_dt}'.")
            st.rerun()

    # ---------------- Active rules ----------------
    st.divider()
    st.subheader("Active rules")
    rules = (db.table("visa_rules")
             .select("route_group, sub_path, chunk_index, section_title, effective_year, created_at")
             .eq("country", country).eq("is_active", True)
             .order("route_group").execute().data or [])
    if rules:
        st.dataframe(rules, use_container_width=True)
    else:
        st.caption("No rules ingested yet.")