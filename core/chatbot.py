from core.retrieval import vector_search_rules, format_rules_context
from core.llm import chat_answer
from core.db import get_db


def ask(user, question, country, route_group=None, check_summary=None):
    rows = vector_search_rules(country, question, route_group)
    ctx = format_rules_context(rows)
    answer = chat_answer(question, ctx, check_summary)

    db = get_db()
    # Read account-level visibility preference
    visible = False
    try:
        pref = (db.table("accounts").select("chat_visible_to_admin")
                .eq("id", user["id"]).execute().data)
        if pref:
            visible = bool(pref[0]["chat_visible_to_admin"])
    except Exception:
        pass

    try:
        db.table("chat_logs").insert({
            "user_id": user["id"],
            "user_message": question,
            "assistant_reply": answer,
            "retrieved_rule_ids": [r["id"] for r in rows],
            "content_visible_to_admin": visible,
        }).execute()
    except Exception:
        pass

    return answer
