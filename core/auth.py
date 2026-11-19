import os
import bcrypt
import streamlit as st
from datetime import datetime, timezone
from core.db import get_db
from core.system_events import log_event


def _get_invite():
    try:
        code = st.secrets.get("INVITE_CODE")
        if code:
            return code
    except Exception:
        pass
    return os.environ.get("INVITE_CODE", "")


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def create_account(username, email, password, role="user"):
    db = get_db()
    if not username or not password:
        return None, "Username and password are required."
    if db.table("accounts").select("id").eq("username", username).execute().data:
        return None, "Username already exists."
    row = {
        "username": username,
        "email": email or None,
        "password_hash": hash_password(password),
        "role": role,
    }
    try:
        res = db.table("accounts").insert(row).execute()
        log_event(res.data[0]["id"], "signup", f"{username} ({role})")
        return res.data[0]["id"], None
    except Exception as e:
        return None, f"Signup failed: {e}"


def authenticate(username, password):
    db = get_db()
    res = db.table("accounts").select("*").eq("username", username).execute()
    if not res.data:
        return None
    acc = res.data[0]
    if not acc.get("is_active"):
        return None
    if not verify_password(password, acc["password_hash"]):
        return None
    db.table("accounts").update(
        {"last_login": datetime.now(timezone.utc).isoformat()}
    ).eq("id", acc["id"]).execute()
    log_event(acc["id"], "login", acc["username"])
    return {
        "id": acc["id"], "username": acc["username"],
        "email": acc.get("email"), "role": acc["role"],
        "chat_visible_to_admin": acc.get("chat_visible_to_admin", False),
    }


def get_user():
    return st.session_state.get("user")


def render_login():
    st.title("VoyaTrace")
    st.caption("Evidence-aware visa compliance engine — Germany (prototype)")
    tab_login, tab_signup = st.tabs(["Login", "Sign up"])

    with tab_login:
        u = st.text_input("Username", key="login_u")
        p = st.text_input("Password", type="password", key="login_p")
        if st.button("Login", type="primary", key="login_btn"):
            acc = authenticate(u, p)
            if acc:
                st.session_state.user = acc
                st.rerun()
            else:
                st.error("Invalid credentials.")
                log_event(None, "login_failed", u, severity="warning")

    with tab_signup:
        st.caption("Users self-register. Parser / Admin accounts require an invite code.")
        new_u = st.text_input("Username", key="signup_u")
        new_e = st.text_input("Email (optional)", key="signup_e")
        new_p = st.text_input("Password", type="password", key="signup_p")
        new_p2 = st.text_input("Confirm password", type="password", key="signup_p2")
        role = st.selectbox("Role", ["user", "parser", "admin"], key="signup_role")
        invite = ""
        if role != "user":
            invite = st.text_input("Invite code", type="password", key="signup_invite")
        if st.button("Create account", key="signup_btn"):
            if new_p != new_p2:
                st.error("Passwords do not match.")
            elif len(new_p) < 6:
                st.error("Password must be at least 6 characters.")
            elif role != "user" and invite != _get_invite():
                st.error("Invalid invite code.")
            else:
                uid, err = create_account(new_u, new_e, new_p, role)
                if err:
                    st.error(err)
                else:
                    st.success("Account created. Log in to continue.")


def render_logout_sidebar():
    with st.sidebar:
        u = st.session_state.user
        st.markdown(f"**{u['username']}**  \n`{u['role']}`")
        if st.button("Logout", key="logout_btn"):
            log_event(u["id"], "logout", u["username"])
            st.session_state.user = None
            st.session_state.chat_history = []
            st.session_state.uploaded_files = {}
            st.session_state.last_check = None
            st.session_state.current_route_key = None
            st.rerun()
        st.divider()
