import streamlit as st

st.set_page_config(page_title="VoyaTrace", layout="wide")

from core.auth import get_user, render_login, render_logout_sidebar
from views import user_check, parser_ingest, admin_dashboard, user_account

user = get_user()
if user is None:
    render_login()
    st.stop()

render_logout_sidebar()

pages = [st.Page(user_check.page, title="Check Compliance", icon="✅")]
if user["role"] in ("parser", "admin"):
    pages.append(st.Page(parser_ingest.page, title="Ingest Rules", icon="📥"))
if user["role"] == "admin":
    pages.append(st.Page(admin_dashboard.page, title="Admin Dashboard", icon="🛡️"))
pages.append(st.Page(user_account.page, title="My Account", icon="👤"))

st.navigation(pages).run()