from core.config import CHUNK_SIZE
from core.embeddings import embed_texts
from core.db import get_db


def chunk_text(text, size=CHUNK_SIZE):
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 2 <= size:
            cur = (cur + "\n\n" + p).strip()
        else:
            if cur:
                chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)
    return chunks


def _deactivate(db, country, route_group, sub_path, section_title):
    """
    Deactivates old rules, but ONLY for the specific section title.
    This prevents overwriting the whole route when adding a new section.
    """
    q = (db.table("visa_rules").update({"is_active": False})
         .eq("country", country).eq("route_group", route_group)
         .eq("section_title", section_title)
         .eq("is_active", True))
    if sub_path:
        q = q.eq("sub_path", sub_path)
    else:
        q = q.is_("sub_path", "null")
    q.execute()


def ingest_route(user_id, country, route_group, sub_path, section_title,
                 text, effective_year=None, source_url=None, source_type=None, verified_at=None):
    db = get_db()
    
    # Deactivate old rules for this specific section before inserting new ones
    _deactivate(db, country, route_group, sub_path, section_title)

    chunks = chunk_text(text)
    vectors = embed_texts(chunks)  # gemini-embedding-001 — parser side only
    rows = []
    for i, (c, v) in enumerate(zip(chunks, vectors)):
        rows.append({
            "country": country,
            "route_group": route_group,
            "sub_path": sub_path,
            "section_title": section_title,
            "chunk_index": i,
            "content": c,
            "embedding": v,
            "effective_year": effective_year,
            "source_url": source_url,
            "source_type": source_type,
            "verified_at": str(verified_at) if verified_at else None,
            "created_by": user_id,
            "is_active": True,
            "version": 1,
        })
        
    if rows:
        db.table("visa_rules").insert(rows).execute()
        
    return len(rows)
