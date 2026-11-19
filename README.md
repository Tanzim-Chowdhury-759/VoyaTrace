# VoyaTrace — Germany Visa Compliance Prototype

Evidence-aware visa document checker. Streamlit + Supabase pgvector + Gemini.

## The locked rules (never break these)

**Vectorize — exactly 2 places, both `gemini-embedding-001`:**
1. Parser ingests embassy rules → chunks embedded → `visa_rules.embedding` (pgvector, permanent)
2. Chatbot query (user question text only) → embed → search rules

**Never vectorize:**
- User's uploaded visa documents (raw PDF → `gemini-2.5-flash-lite` → discarded; only filename/hash/size persisted)
- Admin dashboards and logs (plain PostgreSQL columns)
- Country/visa dropdown lookups (plain SQL `WHERE` filter)

## Setup

1. `pip install -r requirements.txt`
2. Create a Supabase project. Run `database/schema.sql` in the SQL editor.
3. Copy `.env.example` → `.env` and fill in:
   - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `GEMINI_API_KEY`, `INVITE_CODE`
4. Seed Germany routes: