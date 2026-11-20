import hashlib
import uuid
from core.retrieval import (
    fetch_rules_by_filter,
    fetch_required_documents,
    format_rules_context,
)
from core.llm import check_documents
from core.db import get_db
from core.config import MAX_FILE_BYTES, MAX_FILES_PER_CHECK


def _validate_uploads(uploaded_files):
    if len(uploaded_files) > MAX_FILES_PER_CHECK:
        return f"Too many files ({len(uploaded_files)}). Max {MAX_FILES_PER_CHECK}."
    for f in uploaded_files:
        if len(f["bytes"]) > MAX_FILE_BYTES:
            return f"{f['filename']} is larger than {MAX_FILE_BYTES // (1024*1024)} MB."
    return None


def run_compliance_check(user_id, country, route_group, sub_path, uploaded_files):
    """Raw bytes -> Gemini. No vectors on user side, ever."""
    err = _validate_uploads(uploaded_files)
    if err:
        return {"error": err}

    db = get_db()

    rules = fetch_rules_by_filter(country, route_group, sub_path)
    reqs = fetch_required_documents(country, route_group, sub_path)
    
    if not rules:
        return {"error": "No rules found for this route. Ask a parser to ingest them first."}

    # Fetch the strict thresholds (failsafe if table is empty/missing)
    try:
        t_query = (db.table("route_thresholds").select("*")
                   .eq("country", country).eq("route_group", route_group))
        if sub_path:
            t_query = t_query.eq("sub_path", sub_path)
        else:
            t_query = t_query.is_("sub_path", "null")
        thresholds = t_query.execute().data or []
    except Exception:
        thresholds = []

    rules_context = format_rules_context(rules)
    
    # Pass thresholds to the LLM
    result = check_documents(rules_context, reqs, uploaded_files, thresholds)

    session_id = str(uuid.uuid4())

    # Store ONLY metadata — no bytes, no text, no embedding.
    for f in uploaded_files:
        db.table("user_uploads").insert({
            "user_id": user_id,
            "country": country,
            "route_group": route_group,
            "doc_type": f["doc_type"],
            "filename": f["filename"],
            "file_hash": hashlib.sha256(f["bytes"]).hexdigest(),
            "size_bytes": len(f["bytes"]),
            "mime_type": f["mime_type"],
            "status": "checked",
        }).execute()

    # Store structured verdicts — plain columns only.
    for v in result.get("verdicts", []):
        db.table("check_results").insert({
            "user_id": user_id,
            "session_id": session_id,
            "country": country,
            "route_group": route_group,
            "doc_type": v.get("doc_type"),
            "rule_title": v.get("rule_title"),
            "status": v.get("status", "UNKNOWN"),
            "gap_value": v.get("gap_value"),
            "notes": v.get("notes"),
        }).execute()

    return {"session_id": session_id, "result": result}
