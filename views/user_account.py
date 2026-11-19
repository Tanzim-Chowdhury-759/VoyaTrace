import streamlit as st
from core.db import get_db


def page():
    st.title("👤 My Account")
    user = st.session_state.user
    db = get_db()

    st.write(f"**Username:** {user['username']}")
    st.write(f"**Role:** {user['role']}")
    st.write(f"**Email:** {user.get('email') or '—'}")

    # ---------------- Upload metadata ----------------
    st.subheader("My upload metadata")
    ups = (db.table("user_uploads")
           .select("filename, doc_type, route_group, size_bytes, uploaded_at, status")
           .eq("user_id", user["id"])
           .order("uploaded_at", desc=True).execute().data or [])
    st.dataframe(ups, use_container_width=True)
    st.caption(
        "VoyaTrace stores only filenames, sizes, and hashes — never document content."
    )

    # ---------------- Chat visibility ----------------
    st.divider()
    st.subheader("Chat visibility")
    st.caption(
        "VoyaTrace stores your chat messages so you can review them. "
        "By default, admins see only metadata (count, timestamps, tokens) — "
        "never the message content. You can opt in to allow admins to read "
        "your messages for support or debugging. You can turn this off at any time."
    )

    pref_rows = (db.table("accounts").select("chat_visible_to_admin")
                 .eq("id", user["id"]).execute().data or [])
    cur_val = bool(pref_rows[0]["chat_visible_to_admin"]) if pref_rows else False

    new_val = st.toggle(
        "Allow admins to see my chat messages",
        value=cur_val,
        key="chat_visibility_toggle",
    )
    if new_val != cur_val:
        db.table("accounts").update(
            {"chat_visible_to_admin": new_val}
        ).eq("id", user["id"]).execute()
        # Also reflect immediately on existing chat logs
        db.table("chat_logs").update(
            {"content_visible_to_admin": new_val}
        ).eq("user_id", user["id"]).execute()
        st.success("Preference saved.")
        st.rerun()

    # ---------------- Danger zone ----------------
    st.divider()
    st.subheader("Danger zone")
    if st.checkbox("I understand deleting my account is permanent.",
                   key="del_account_check"):
        if st.button("Delete my account", type="primary", key="del_account_btn"):
            db.table("accounts").delete().eq("id", user["id"]).execute()
            st.session_state.user = None
            st.session_state.chat_history = []
            st.session_state.uploaded_files = {}
            st.session_state.last_check = None
            st.success("Account deleted.")
            st.rerun()