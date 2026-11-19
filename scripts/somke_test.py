"""python -m scripts.smoke_test"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv()

from core.config import SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY
from core.db import get_db
from core.embeddings import embed_one


def step(label, fn):
    print(f"→ {label} … ", end="", flush=True)
    try:
        fn()
        print("✅")
    except Exception as e:
        print(f"❌  {e}")
        sys.exit(1)


def _env():
    assert SUPABASE_URL, "SUPABASE_URL missing"
    assert SUPABASE_KEY, "SUPABASE_SERVICE_KEY missing"
    assert GEMINI_API_KEY, "GEMINI_API_KEY missing"


def _tables():
    db = get_db()
    for t in ("accounts", "visa_rules", "required_documents",
              "user_uploads", "check_results", "chat_logs", "system_events"):
        db.table(t).select("*").limit(1).execute()


def _columns():
    db = get_db()
    # New columns from the fixed schema
    db.table("accounts").select("chat_visible_to_admin").limit(1).execute()
    db.table("check_results").select("rule_title").limit(1).execute()


def _seeded():
    db = get_db()
    n = (db.table("visa_rules").select("id", count="exact")
         .eq("country", "Germany").eq("is_active", True).execute().count)
    assert n and n > 0, "No Germany rules seeded — run `python -m scripts.seed_germany`"
    print(f"(Germany active rules: {n}) ", end="")


def _embed():
    v = embed_one("smoke test")
    assert len(v) == 3072, f"Expected 3072-dim, got {len(v)}"


step("env vars", _env)
step("supabase tables", _tables)
step("new columns present", _columns)
step("Germany seed present", _seeded)
step("gemini-embedding-001", _embed)
print("\nAll checks passed — ready to deploy.")