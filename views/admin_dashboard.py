import streamlit as st
from core.db import get_db


def page():
    st.title("🛡️ Admin Dashboard")
    if st.session_state.user["role"] != "admin":
        st.error("Admins only.")
        return

    db = get_db()

    # ---------------- Accounts ----------------
    st.subheader("Accounts")
    accs = (db.table("accounts")
            .select("username, email, role, is_active, chat_visible_to_admin, "
                    "created_at, last_login")
            .order("created_at", desc=True).execute().data or [])
    st.dataframe(accs, use_container_width=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Users", sum(1 for a in accs if a["role"] == "user"))
    c2.metric("Parsers", sum(1 for a in accs if a["role"] == "parser"))
    c3.metric("Active accounts", sum(1 for a in accs if a["is_active"]))

    # ---------------- Checks ----------------
    st.subheader("Recent checks")
    checks = (db.table("check_results")
              .select("user_id, route_group, doc_type, rule_title, status, created_at")
              .order("created_at", desc=True).limit(50).execute().data or [])
    st.dataframe(checks, use_container_width=True)

    # ---------------- System events ----------------
    st.subheader("System events")
    events = (db.table("system_events")
              .select("event_type, detail, severity, created_at")
              .order("created_at", desc=True).limit(50).execute().data or [])
    st.dataframe(events, use_container_width=True)

    # ---------------- Chat activity ----------------
    st.subheader("Chat activity")
    chats = (db.table("chat_logs")
             .select("user_id, user_message, assistant_reply, tokens_used, "
                     "error, created_at, content_visible_to_admin")
             .order("created_at", desc=True).limit(100).execute().data or [])

    summary_rows = [{
        "user_id": (c["user_id"][:8] + "…") if c.get("user_id") else "—",
        "tokens": c.get("tokens_used") or 0,
        "error": c.get("error") or "",
        "at": c.get("created_at"),
        "content_visible": c.get("content_visible_to_admin", False),
    } for c in chats]
    st.dataframe(summary_rows, use_container_width=True)
    st.caption(
        "Message content is hidden by default. It appears below only for users "
        "who opted in via 'My Account → Chat visibility'."
    )

    opted = [c for c in chats if c.get("content_visible_to_admin")]
    if opted:
        with st.expander(f"Show content for {len(opted)} opted-in message(s)"):
            for c in opted[:20]:
                uid = (c["user_id"][:8] + "…") if c.get("user_id") else "—"
                st.markdown(f"**{c['created_at']}** — `{uid}`")
                st.markdown(f"> **User:** {c.get('user_message') or '—'}")
                st.markdown(f"> **VoyaTrace:** {c.get('assistant_reply') or '—'}")
                st.divider()
    else:
        st.info("No user has opted in to share chat content.")

    st.caption(
        "Admin cannot view or modify the `visa_rules` vector table directly. "
        "That belongs to parsers."
    )
