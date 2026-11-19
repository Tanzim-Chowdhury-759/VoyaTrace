import os
import streamlit as st

def _get(key, default=None):
    try:
        val = st.secrets.get(key)
        if val:
            return val
    except Exception:
        pass
    return os.environ.get(key, default)

SUPABASE_URL = _get("SUPABASE_URL")
SUPABASE_KEY = _get("SUPABASE_SERVICE_KEY")
GEMINI_API_KEY = _get("GEMINI_API_KEY")

EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 3072
CHAT_MODEL = "gemini-2.5-flash-lite"
CHECK_MODEL = "gemini-2.5-flash-lite"

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
TOP_K_RETRIEVAL = 6

# Per-upload sanity limits (protects free-tier quota + UI responsiveness)
MAX_FILE_BYTES = 8 * 1024 * 1024    # 8 MB per file
MAX_FILES_PER_CHECK = 8

ALLOWED_COUNTRIES = ["Germany"]