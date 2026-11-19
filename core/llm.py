import json
from google import genai
from google.genai import types
from core.config import GEMINI_API_KEY, CHECK_MODEL, CHAT_MODEL

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


_SUPPORTED_BINARY_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def check_documents(rules_context, required_docs, uploaded_files):
    """
    Raw user bytes -> gemini-2.5-flash-lite in ONE call.
    No text extraction. No embeddings. No persistence.
    """
    client = _get_client()
    parts = []

    parts.append(types.Part.from_text(
        text="OFFICIAL EMBASSY RULES (retrieved from VoyaTrace knowledge base):\n\n"
             + rules_context))

    req_lines = "\n".join(
        f"- {d['doc_type']}: {d['doc_label']} (required={d.get('is_required')})"
        + (f" [{d.get('evidence_label')}]" if d.get("evidence_label") else "")
        for d in required_docs)
    parts.append(types.Part.from_text(text="REQUIRED DOCUMENTS:\n" + req_lines))

    for f in uploaded_files:
        parts.append(types.Part.from_text(
            text=f"\n===== UPLOADED DOCUMENT: {f['doc_type']} ({f['filename']}) ====="))
        if f["mime_type"] in _SUPPORTED_BINARY_MIMES:
            parts.append(types.Part.from_bytes(data=f["bytes"], mime_type=f["mime_type"]))
        else:
            try:
                text = f["bytes"].decode("utf-8", errors="replace")
            except Exception:
                text = "(unreadable)"
            parts.append(types.Part.from_text(text=text))

    parts.append(types.Part.from_text(text="""
You are a visa compliance checker. Compare the user's uploaded documents against the rules above.
Return verdicts for each required document and each numbered rule that appears in the rules text:
- PASS: document clearly satisfies the rule.
- FAIL: present but numeric/factual gap (e.g. salary below threshold). Compute exact gap.
- MISSING: document not uploaded, or required fact not stated.
- UNKNOWN: cannot determine.

Rules:
1. Never guarantee a visa outcome. Never check for forgery.
2. Extract exact numbers/dates verbatim.
3. If the rules text flags a source conflict (e.g. outdated embassy figures), use the newer 2026 figure and note the discrepancy.

Return ONLY JSON:
{
  "verdicts": [
    {"rule_title": "...", "doc_type": "...", "status": "PASS|FAIL|MISSING|UNKNOWN",
     "gap_value": "...", "notes": "..."}
  ],
  "summary": "one-paragraph plain-English summary",
  "next_steps": ["...", "..."]
}
"""))

    resp = client.models.generate_content(
        model=CHECK_MODEL,
        contents=parts,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    try:
        return json.loads(resp.text)
    except Exception:
        return {"verdicts": [], "summary": resp.text, "next_steps": [],
                "error": "json_parse_failed"}


def chat_answer(question, rules_context, check_summary=None):
    client = _get_client()
    system = (
        "You are VoyaTrace, a visa-document assistant. Answer ONLY from the retrieved official rules "
        "and the user's own check results below. If the answer is not in the context, reply exactly: "
        "'I don't have an official rule for that — verify with the embassy.' "
        "Never guarantee a visa outcome. Never invent figures or deadlines. "
        "When quoting a number, note that it comes from the stored rule and the embassy may update it. "
        "Never advise on fraud, forgery, or misrepresentation."
    )
    ctx = f"RETRIEVED OFFICIAL RULES:\n{rules_context}\n\n"
    if check_summary:
        ctx += f"USER'S LAST CHECK SUMMARY:\n{check_summary}\n\n"
    ctx += f"USER QUESTION: {question}"

    resp = client.models.generate_content(
        model=CHAT_MODEL,
        contents=[
            types.Part.from_text(text=system),
            types.Part.from_text(text=ctx),
        ],
    )
    return resp.text