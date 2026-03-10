"""
Koach OS v2 — Memory Engine (Vector-based RAG)
================================================
Embeds conversations into ChromaDB for semantic recall.
Past relevant context is automatically injected into prompts.

Future: Switch embedding to RunPod-hosted model for cost/speed.
Future: Voice conversation support.
"""

from pathlib import Path
from data_manager import get_secret, timestamp_jst, generate_id

MEMORY_DB_DIR = Path(__file__).parent / "memory" / "vector_db"


def _get_collection():
    """Get or create the conversations collection."""
    import chromadb

    MEMORY_DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(MEMORY_DB_DIR))
    return client.get_or_create_collection(
        name="conversations",
        metadata={"hnsw:space": "cosine"},
    )


def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings using OpenAI API."""
    import openai

    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not configured")

    client = openai.OpenAI(api_key=api_key)
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=[t[:8000] for t in texts],
    )
    return [d.embedding for d in resp.data]


def store_conversation(
    conversation_id: str,
    user_message: str,
    ai_response: str,
    domain: str = "",
    task_type: str = "",
    intervention_level: str = "",
) -> None:
    """Embed and store a conversation exchange."""
    collection = _get_collection()

    combined = f"User: {user_message}\nAssistant: {ai_response}"

    try:
        embeddings = _embed_texts([combined])
    except Exception:
        return  # Don't break chat flow

    meta = {
        "domain": domain,
        "task_type": task_type,
        "intervention_level": intervention_level,
        "timestamp": timestamp_jst(),
        "user_message": user_message[:500],
        "ai_response_preview": ai_response[:500],
    }

    collection.add(
        ids=[conversation_id],
        embeddings=embeddings,
        documents=[combined[:2000]],
        metadatas=[meta],
    )


def recall_similar(query: str, n: int = 5, domain: str = None) -> list[dict]:
    """Find similar past conversations by semantic similarity."""
    collection = _get_collection()

    if collection.count() == 0:
        return []

    try:
        embeddings = _embed_texts([query])
    except Exception:
        return []

    kwargs = {
        "query_embeddings": embeddings,
        "n_results": min(n, collection.count()),
        "include": ["documents", "metadatas", "distances"],
    }
    if domain:
        kwargs["where"] = {"domain": domain}

    results = collection.query(**kwargs)

    memories = []
    for i, doc in enumerate(results["documents"][0]):
        memories.append({
            "content": doc,
            "metadata": results["metadatas"][0][i],
            "relevance": 1 - results["distances"][0][i],
        })

    return memories


def get_memory_context(
    query: str, n: int = 3, domain: str = None, min_relevance: float = 0.3
) -> str:
    """Get formatted memory context string for prompt injection."""
    memories = recall_similar(query, n=n, domain=domain)

    relevant = [m for m in memories if m["relevance"] >= min_relevance]
    if not relevant:
        return ""

    parts = ["RECALLED MEMORIES (from past conversations):"]
    for i, m in enumerate(relevant, 1):
        ts = m["metadata"].get("timestamp", "")
        domain_tag = m["metadata"].get("domain", "")
        relevance_pct = f"{m['relevance']:.0%}"
        parts.append(f"\n[Memory {i}] ({domain_tag}, {ts}, relevance: {relevance_pct})")
        parts.append(m["content"][:500])

    parts.append("\nUse these memories to provide continuity and context-aware responses.")
    return "\n".join(parts)


def get_memory_stats() -> dict:
    """Get statistics about stored memories."""
    try:
        collection = _get_collection()
        return {"total_memories": collection.count(), "status": "active"}
    except Exception:
        return {"total_memories": 0, "status": "not_initialized"}
