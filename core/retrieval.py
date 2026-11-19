from core.db import get_db
from core.embeddings import embed_one
from core.config import TOP_K_RETRIEVAL


def fetch_rules_by_filter(country, route_group, sub_path=None):
    """Exact lookup — plain SQL WHERE. NO embedding."""
    db = get_db()
    if sub_path:
        rows_sub = (db.table("visa_rules").select("*")
                    .eq("country", country).eq("route_group", route_group)
                    .eq("sub_path", sub_path).eq("is_active", True)
                    .order("chunk_index").execute().data or [])
        rows_gen = (db.table("visa_rules").select("*")
                    .eq("country", country).eq("route_group", route_group)
                    .is_("sub_path", "null").eq("is_active", True)
                    .order("chunk_index").execute().data or [])
        return rows_gen + rows_sub
    return (db.table("visa_rules").select("*")
            .eq("country", country).eq("route_group", route_group)
            .is_("sub_path", "null").eq("is_active", True)
            .order("chunk_index").execute().data or [])


def fetch_required_documents(country, route_group, sub_path=None):
    db = get_db()
    if sub_path:
        rows_sub = (db.table("required_documents").select("*")
                    .eq("country", country).eq("route_group", route_group)
                    .eq("sub_path", sub_path)
                    .order("display_order").execute().data or [])
        rows_gen = (db.table("required_documents").select("*")
                    .eq("country", country).eq("route_group", route_group)
                    .is_("sub_path", "null")
                    .order("display_order").execute().data or [])
        # de-dupe by doc_type (sub-path wins over general)
        seen = {r["doc_type"] for r in rows_sub}
        merged = [r for r in rows_gen if r["doc_type"] not in seen] + rows_sub
        merged.sort(key=lambda r: r.get("display_order") or 0)
        return merged
    return (db.table("required_documents").select("*")
            .eq("country", country).eq("route_group", route_group)
            .is_("sub_path", "null")
            .order("display_order").execute().data or [])


def vector_search_rules(country, query, route_group=None, top_k=TOP_K_RETRIEVAL):
    """Chatbot query embedding — the ONLY other embedding site."""
    db = get_db()
    qv = embed_one(query)
    try:
        res = db.rpc("match_visa_rules", {
            "query_embedding": qv, "match_count": top_k,
            "filter_country": country, "filter_route_group": route_group,
        }).execute()
        return res.data or []
    except Exception:
        rows = (db.table("visa_rules").select("*")
                .eq("country", country).eq("is_active", True).execute().data or [])
        import math
        def cos(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(y * y for y in b))
            return dot / (na * nb + 1e-9)
        rows.sort(key=lambda r: cos(qv, r["embedding"]), reverse=True)
        return rows[:top_k]


def format_rules_context(rows):
    return "\n\n".join(
        f"[{r['route_group']}"
        f"{('/' + r['sub_path']) if r.get('sub_path') else ''} · "
        f"{r.get('section_title','')}]\n{r['content']}"
        for r in rows)