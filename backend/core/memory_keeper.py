"""Memory Keeper — organisational memory service.

Runs silently in the background — never speaks in debates, only emits
system events. Wraps ChromaDB for persistent vector storage of debate
summaries.

Two jobs:
  1. BEFORE debate: recall() → queries ChromaDB for top 3 relevant past
     memories, emits memory_recall event, returns memories for context injection.
  2. AFTER debate:  store()   → persists compressed summary + tags into
     ChromaDB, emits memory_stored event.

Emits: memory_recall, memory_stored
"""

import json
from typing import TYPE_CHECKING

import chromadb
from chromadb.utils import embedding_functions

if TYPE_CHECKING:
    from fastapi import WebSocket


class MemoryKeeper:
    """Organisational memory service — ChromaDB-backed, event-emitting."""

    def __init__(self, chroma_client, ws_broadcaster=None):
        self.client = chroma_client
        self.ef = embedding_functions.DefaultEmbeddingFunction()
        self.col = self.client.get_or_create_collection(
            name="debate_memories",
            embedding_function=self.ef,
            metadata={"description": "AI Startup Boardroom debate summaries"},
        )
        self.broadcast = ws_broadcaster  # async callable: broadcast(event_dict)

    def set_broadcaster(self, ws_broadcaster) -> None:
        """Set or update the broadcast function (per-debate WebSocket)."""
        self.broadcast = ws_broadcaster

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def recall(self, problem: str, debate_id: str) -> list[str]:
        """Query ChromaDB for the 3 most relevant past memories.

        Called by orchestrator BEFORE debate starts.

        Returns the list of memory strings (empty list if first debate).
        """
        try:
            total = self.col.count()
            if total == 0:
                return []

            # Never request more results than documents stored
            n = min(3, total)
            results = self.col.query(query_texts=[problem], n_results=n)
            memories = results["documents"][0] if results["documents"] else []
            scores = results["distances"][0] if results["distances"] else []

            # Convert distances to relevance scores (1 - normalised distance)
            relevance = [round(1 - min(d, 1.0), 2) for d in scores]

            event = {
                "type": "memory_recall",
                "debate_id": debate_id,
                "memories": memories,
                "relevance_scores": relevance,
                "total_stored": total,   # send total count not just recalled count
            }
            if self.broadcast:
                await self.broadcast(event)

            return memories

        except Exception as e:
            print(f"[MEMORY] recall error: {e}")
            return []

    async def store(
        self, debate_id: str, debate_summary: str, tags: list[str]
    ) -> None:
        """Store a compressed debate summary after debate ends.

        Called by orchestrator AFTER the debate completes.
        """
        try:
            self.col.upsert(
                documents=[debate_summary],
                ids=[debate_id],
                metadatas=[{"tags": json.dumps(tags), "debate_id": debate_id}],
            )

            event = {
                "type": "memory_stored",
                "debate_id": debate_id,
                "summary": (
                    debate_summary[:200] + "..."
                    if len(debate_summary) > 200
                    else debate_summary
                ),
                "tags": tags,
            }
            if self.broadcast:
                await self.broadcast(event)

        except Exception as e:
            print(f"[MEMORY] store error for {debate_id}: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def build_memory_context(self, memories: list[str]) -> str:
        """Format recalled memories into a context block injected into
        agent prompts before the debate.
        """
        if not memories:
            return "No relevant organisational memory found for this problem."

        lines = ["ORGANISATIONAL MEMORY (from past debates):"]
        for i, m in enumerate(memories, 1):
            lines.append(f"{i}. {m}")
        return "\n".join(lines)

    def count(self) -> int:
        """Number of stored memories."""
        return self.col.count()
