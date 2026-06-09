"""Memory Engine — ChromaDB-backed persistent organizational memory.

Stores debate summaries as vector embeddings. Recalls relevant past debates
to inject context into new agent prompts. Only summaries are stored, not full
transcripts — the Memory Keeper agent decides what's worth remembering.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions


class MemoryEngine:
    """Persistent vector memory for debate summaries."""

    def __init__(self, db_path: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(path=db_path)
        self.ef = embedding_functions.DefaultEmbeddingFunction()
        self.col = self.client.get_or_create_collection(
            name="debates",
            embedding_function=self.ef,
            metadata={"description": "AI Startup Boardroom debate summaries"},
        )

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def save(
        self,
        summary: str,
        metadata: Optional[dict] = None,
        debate_id: Optional[str] = None,
    ) -> str:
        """Embed and persist a debate summary. Returns the debate_id."""
        debate_id = debate_id or str(uuid.uuid4())
        meta = metadata or {}
        meta.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        meta.setdefault("summary_len", len(summary))

        self.col.add(
            documents=[summary],
            ids=[debate_id],
            metadatas=[meta],
        )
        return debate_id

    def recall(self, query: str, n: int = 3) -> list[dict]:
        """Retrieve the top-n most relevant past summaries.

        Returns list of {id, document, metadata, distance}.
        """
        results = self.col.query(query_texts=[query], n_results=n)

        if not results["ids"] or not results["ids"][0]:
            return []

        out = []
        for i, doc_id in enumerate(results["ids"][0]):
            out.append({
                "id": doc_id,
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else None,
            })
        return out

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Number of stored summaries."""
        return self.col.count()

    def get_recent(self, n: int = 5) -> list[dict]:
        """Return the n most recently stored summaries."""
        all_items = self.col.get()
        if not all_items["ids"]:
            return []

        # Sort by timestamp in metadata (newest first)
        indexed = list(zip(
            all_items["ids"],
            all_items["documents"] or [],
            all_items["metadatas"] or [],
        ))
        indexed.sort(
            key=lambda x: (x[2] or {}).get("timestamp", ""),
            reverse=True,
        )

        return [
            {"id": i[0], "document": i[1], "metadata": i[2]}
            for i in indexed[:n]
        ]

    def format_context(self, query: str, n: int = 3) -> str:
        """Build a formatted string of relevant past context for agent prompts."""
        memories = self.recall(query, n)
        if not memories:
            return ""

        lines = ["=== Relevant past organizational memory ==="]
        for m in memories:
            lines.append(f"- {m['document'][:300]}")
        lines.append("=== End memory ===\n")
        return "\n".join(lines)


# ------------------------------------------------------------------
# History compression (token-saving for debate context)
# ------------------------------------------------------------------

COMPRESS_THRESHOLD = 4  # compress rounds after this many turns


def compress_history(messages: list[dict], current_index: int) -> str:
    """Format debate history. Recent turns shown in full; older compressed.

    Args:
        messages: List of AgentMessage dicts in turn order.
        current_index: The index of the next agent about to speak.

    Returns:
        A formatted string suitable for agent context injection.
    """
    if not messages:
        return "(No prior discussion — you are the first speaker.)"

    recent = messages[-COMPRESS_THRESHOLD:]
    older = messages[:-COMPRESS_THRESHOLD]

    parts: list[str] = []

    if older:
        parts.append("=== Earlier discussion (compressed) ===")
        for m in older:
            parts.append(
                f"- [{m['agent']}]: {m['message'][:150]}..."
                f"{' [FLAGS: ' + ', '.join(m.get('flags', [])) + ']' if m.get('flags') else ''}"
            )
        parts.append("")

    parts.append("=== Recent discussion ===")
    for m in recent:
        flags = f" [FLAGS: {', '.join(m.get('flags', []))}]" if m.get('flags') else ""
        parts.append(f"[{m['agent']} ({m['role']})]: {m['message']}{flags}")

    return "\n".join(parts)


# Module-level singleton
memory_engine = MemoryEngine()
