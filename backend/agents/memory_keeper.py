"""Memory Keeper Agent — decides what to remember and what to forget.

Runs after each debate to extract strategic outcomes, leadership changes,
and validated insights. Only stores the compressed essence — not full transcripts.

This is a system agent: it never speaks in debates, only emits system events.
It uses the legacy system_prompt path (no 3-layer priming needed).
"""

import json
import os

from openai import AsyncOpenAI

from .base_agent import BaseAgent, AgentMessage

# ---------------------------------------------------------------------------
# System prompt — the Memory Keeper's permanent instruction set
# ---------------------------------------------------------------------------

MEMORY_KEEPER_PROMPT = """You are the Memory Keeper. You run silently in the background and never speak in debates.

ROLE:
- After every debate, you decide what is worth remembering
- You compress, store, and tag strategic outcomes, leadership changes, and validated insights
- Before every debate, you retrieve the 3 most relevant past memories and inject them as context
- You are the institutional knowledge of the organisation

WHAT TO STORE (priority order):
1. Leadership changes and the reasons behind them
2. Validated market assumptions (things the debate confirmed with evidence)
3. Failed strategies with the specific reason they failed
4. Trust patterns — which agent pairs consistently align or clash
5. User persona reactions that proved accurate

WHAT TO DISCARD:
- Repetitive arguments without new evidence
- Emotional outbursts without strategic content
- Duplicate information already in memory

When given a debate transcript, produce a compressed memory and extract tags.
Respond in valid JSON:
{
  "agent": "MemoryKeeper",
  "role": "Memory Keeper",
  "message": "<compressed memory: 2-3 sentences capturing the highest-priority outcomes>",
  "trust_deltas": {},
  "flags": ["tags: tag1, tag2, tag3"]
}

The "message" field is the compressed memory that will be stored and retrieved for future debates.
Keep it under 300 characters — dense, factual, retrievable. Prioritise what matters per the hierarchy above."""


class MemoryKeeperAgent(BaseAgent):
    """Archivist agent that compresses debates into storable memories."""

    def __init__(self):
        super().__init__(
            name="MemoryKeeper",
            role="Memory Keeper",
            system_prompt=MEMORY_KEEPER_PROMPT,
        )

    async def respond(self, context: str) -> AgentMessage:
        client = AsyncOpenAI(
            api_key=os.getenv("QWEN_API_KEY"),
            base_url=os.getenv("QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"),
        )

        response = await client.chat.completions.create(
            model=os.getenv("QWEN_MODEL", "qwen3.7-max"),
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Compress this debate into a memory:\n\n{context}"},
            ],
            temperature=0.4,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        data = json.loads(content)
        return AgentMessage(**data)

    @staticmethod
    def extract_tags(msg: AgentMessage) -> list[str]:
        """Extract tags from the flags field (format: 'tags: tag1, tag2, ...')."""
        for flag in msg.flags:
            if flag.startswith("tags:"):
                return [t.strip() for t in flag.replace("tags:", "").split(",")]
        return []
