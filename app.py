import streamlit as st

st.set_page_config(page_title="VoyaTrace", layout="wide")

from core.auth import get_user, render_login, render_logout_sidebar
from views import user_check, parser_ingest, admin_dashboard, user_account

# --- HIDE SIDEBAR IF LOGGED OUT ---
user = get_user()
if user is None:
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] {
                display: none;
            }
        </style>
        """,
        unsafe_allow_html=True
    )
    render_login()
    st.stop()

# --- LOGGED IN UI ---
render_logout_sidebar()

# Explicitly defining url_path prevents Streamlit from guessing and colliding
pages = [
    st.Page(user_check.page, title="Check Compliance", icon="✅", url_path="check")
]

if user["role"] in ("parser", "admin"):
    pages.append(st.Page(parser_ingest.page, title="Ingest Rules", icon="📥", url_path="ingest"))

if user["role"] == "admin":
    pages.append(st.Page(admin_dashboard.page, title="Admin Dashboard", icon="🛡️", url_path="admin"))

pages.append(st.Page(user_account.page, title="My Account", icon="👤", url_path="account"))

st.navigation(pages).run()
