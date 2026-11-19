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


def _deactivate(db, country, route_group, sub_path):
    q = (db.table("visa_rules").update({"is_active": False})
         .eq("country", country).eq("route_group", route_group)
         .eq("is_active", True))
    if sub_path:
        q = q.eq("sub_path", sub_path)
    else:
        q = q.is_("sub_path", "null")
    q.execute()


def ingest_route(user_id, country, route_group, sub_path, section_title,
                 text, effective_year=None, source_url=None):
    db = get_db()
    _deactivate(db, country, route_group, sub_path)

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
            "created_by": user_id,
            "is_active": True,
            "version": 1,
        })
    if rows:
        db.table("visa_rules").insert(rows).execute()
    return len(rows)