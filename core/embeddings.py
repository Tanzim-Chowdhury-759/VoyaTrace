from google import genai
from core.config import GEMINI_API_KEY, EMBED_MODEL

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client

def embed_texts(texts):
    """Embed a list of texts. Used ONLY for embassy rules + chatbot queries."""
    client = _get_client()
    out = []
    for t in texts:
        r = client.models.embed_content(model=EMBED_MODEL, contents=t)
        out.append(list(r.embeddings[0].values))
    return out

def embed_one(text):
    return embed_texts([text])[0]
