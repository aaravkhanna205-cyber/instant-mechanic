"""On-demand local embeddings; no external LLM or automatic selection."""
from functools import lru_cache
MODEL_ID='sentence-transformers/all-MiniLM-L6-v2'
DIMENSIONS=384
@lru_cache(maxsize=1)
def model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_ID)
def embed(texts: list[str]) -> list[list[float]]:
    if not texts: return []
    if any(not t.strip() for t in texts): raise ValueError('Empty text')
    output = model().encode(texts,normalize_embeddings=True,show_progress_bar=False)
    return [[float(v) for v in row] for row in output]
