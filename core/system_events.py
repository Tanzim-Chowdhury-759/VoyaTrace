from core.db import get_db


def log_event(actor_id, event_type, detail="", severity="info"):
    try:
        get_db().table("system_events").insert({
            "actor_id": actor_id,
            "event_type": event_type,
            "detail": detail,
            "severity": severity,
        }).execute()
    except Exception:
        pass