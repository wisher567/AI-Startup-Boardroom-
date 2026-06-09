"""Base agent class and AgentMessage schema.

Supports the 3-layer prompt architecture:
  Layer 1 — Personality Core (fixed, never changes)
  Layer 2 — Dynamic Context (filled by primer per debate)
  Layer 3 — Behaviour Rules (fixed, never changes)

System agents (MemoryKeeper etc.) can bypass this by passing a plain
system_prompt string — they don't need per-debate dynamic context.

Shared LLM infrastructure:
  - _create_client() — returns a configured AsyncOpenAI client
  - _stream_and_collect() — handles streaming response accumulation
"""

import os
import json
from pydantic import BaseModel
from openai import AsyncOpenAI


class AgentMessage(BaseModel):
    agent: str
    role: str
    message: str
    trust_deltas: dict[str, float] = {}
    flags: list[str] = []


class BaseAgent:
    """Every debate agent inherits from this.

    Two construction paths:
      1) 3-layer prompt: pass personality_core + dynamic_template + behaviour_rules
      2) Legacy / system agent: pass system_prompt directly
    """

    def __init__(
        self,
        name: str,
        role: str,
        system_prompt: str | None = None,
        personality_core: str | None = None,
        dynamic_template: str | None = None,
        behaviour_rules: str | None = None,
    ):
        self.name = name
        self.role = role

        # 3-layer mode
        self.personality_core = personality_core or ""
        self.dynamic_template = dynamic_template or ""
        self.behaviour_rules = behaviour_rules or ""
        self.dynamic_context: dict[str, str] = {}
        self.learned_stance = ""  # injected by LearningEngine before debate

        # Resolve system_prompt: use the 3-layer build if layers are provided,
        # otherwise fall back to the passed-in string.
        if personality_core or dynamic_template or behaviour_rules:
            self.system_prompt = self.build_system_prompt()
        else:
            self.system_prompt = system_prompt or ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def inject_context(self, context_dict: dict[str, str]) -> None:
        """Fill dynamic placeholders from the primer or Persona Factory.

        Called once per debate, before the agent speaks.  Uses simple
        string replacement so missing keys never throw — and memory_context
        defaults to empty string so the first-ever debate (no memories yet)
        never leaks a raw {memory_context} placeholder into the LLM prompt.

        Rebuilds system_prompt so every subsequent respond() call uses
        the personalised context.
        """
        self.dynamic_context = context_dict

        if not self.dynamic_template:
            return  # nothing to fill

        # Start from the full 3-layer prompt (placeholders still raw)
        self.context_prompt = self.system_prompt

        # memory_context always has a safe fallback
        ctx: dict[str, str] = {"memory_context": "", **context_dict}

        for key, value in ctx.items():
            self.context_prompt = self.context_prompt.replace(
                f"{{{key}}}", str(value)
            )

        # Any remaining unreplaced {placeholders} stay as-is — the primer
        # should have covered them, but it's safe either way.

        # Update system_prompt so respond() uses the filled version
        self.system_prompt = self.context_prompt

    def inject_learned_stance(self, stance: str):
        """
        Inject this agent's learned stance as a 4th layer.
        Called by orchestrator before debate starts, after inject_context().
        """
        if not stance:
            return
        self.learned_stance = stance
        # Append to the already-injected context prompt
        self.context_prompt += f"\n\n--- WHAT YOU HAVE LEARNED FROM PAST DEBATES ---\n{stance}\n\nThis shapes how you argue today. Your past experience is real — use it."
        self.system_prompt = self.context_prompt

    def build_system_prompt(self) -> str:
        """Combine all three layers into the initial system prompt.

        Returns the raw 3-layer prompt with placeholders intact.  The
        actual filling happens in inject_context() — this just assembles
        the template.

        If no dynamic_template is set (system agents), returns the raw
        personality_core (which acts as the full prompt).
        """
        if not self.dynamic_template:
            # System-agent / legacy path — personality_core *is* the prompt
            return self.personality_core or self.system_prompt

        prompt = (
            f"{self.personality_core}\n\n"
            f"{self.dynamic_template}\n\n"
            f"{self.behaviour_rules}"
        )
        # Inject the AgentMessage JSON schema with THIS agent's exact identity
        prompt += (
            f'\n\n--- AgentMessage JSON schema ---\n'
            f'You MUST respond with ONLY this JSON structure:\n'
            f'{{"agent": "{self.name}", "role": "{self.role}", '
            f'"message": "<your response>", "trust_deltas": {{}}, "flags": []}}\n'
            f'CRITICAL: The "agent" field MUST be exactly "{self.name}". '
            f'The "role" field MUST be exactly "{self.role}". '
            f'Do not change these values. Do not use display names or persona names.'
        )
        return prompt

    # ------------------------------------------------------------------
    # Tool call parsing
    # ------------------------------------------------------------------

    def parse_tool_calls(self, flags: list[str]) -> list[tuple[str, str]]:
        """Parse tool call flags from agent response.

        Returns list of (tool_name, query) tuples.
        Example: "tool_call:web_search:food delivery Sri Lanka competitors"
        -> ("web_search", "food delivery Sri Lanka competitors")
        """
        tool_calls = []
        for flag in flags:
            if flag.startswith("tool_call:"):
                parts = flag.split(":", 2)
                if len(parts) == 3:
                    tool_calls.append((parts[1], parts[2]))
        return tool_calls

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_format(template: str, context: dict[str, str]) -> str:
        """Format a template, leaving missing keys as visible placeholders."""
        result = template
        for key, value in context.items():
            result = result.replace("{" + key + "}", value)
        # Any remaining {placeholders} stay as-is — the LLM sees them
        return result

    def has_dynamic_context(self) -> bool:
        """Return True if this agent uses 3-layer prompts (needs priming)."""
        return bool(self.dynamic_template)

    def get_placeholder_keys(self) -> list[str]:
        """Return the ordered placeholder keys this agent expects from the primer.

        Parses {key_name} patterns from the dynamic_template.  The primer
        uses this to know exactly which keys to generate for each agent.
        """
        import re
        seen: set[str] = set()
        keys: list[str] = []
        for match in re.finditer(r"\{(\w+)\}", self.dynamic_template):
            key = match.group(1)
            if key not in seen:
                seen.add(key)
                keys.append(key)
        return keys

    def get_spec_for_primer(self) -> str:
        """A compact one-liner for the primer: 'CEO: problem_context, ceo_position, ceo_concern, ceo_question'"""
        keys = self.get_placeholder_keys()
        return f"{self.name}: {', '.join(keys)}"

    # ------------------------------------------------------------------
    # Shared LLM infrastructure
    # ------------------------------------------------------------------

    def _get_base_url(self) -> str:
        """Base URL for the LLM API. Override per agent if needed."""
        return os.getenv("QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")

    def _create_client(self) -> AsyncOpenAI:
        """Return a configured AsyncOpenAI client."""
        return AsyncOpenAI(
            api_key=os.getenv("QWEN_API_KEY"),
            base_url=self._get_base_url(),
        )

    def _get_model(self) -> str:
        """Return the model name. Override per agent if needed."""
        return os.getenv("QWEN_MODEL", "qwen3.7-max")

    def _get_temperature(self) -> float:
        """Return the temperature. Override per agent for different styles."""
        return 0.7

    async def _stream_and_collect(self, response, on_token=None) -> str:
        """Accumulate streaming chunks, calling on_token(text) for each.

        Returns the full assembled content string.
        """
        chunks: list[str] = []
        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                text = delta.content
                chunks.append(text)
                if on_token:
                    await on_token(text)
        return "".join(chunks)

    # ------------------------------------------------------------------
    # Retry wrapper
    # ------------------------------------------------------------------

    async def _retry_respond(
        self, context: str, on_token=None, max_retries: int = 2
    ) -> AgentMessage:
        """Call respond() with retry on connection errors."""
        import asyncio as _asyncio
        last_err = None
        for attempt in range(max_retries + 1):
            try:
                return await self.respond(context, on_token=on_token)
            except Exception as e:
                last_err = e
                if attempt < max_retries:
                    wait = (attempt + 1) * 3  # 3s, 6s backoff
                    await _asyncio.sleep(wait)
        raise last_err  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Subclass hook
    # ------------------------------------------------------------------

    async def respond(self, context: str, on_token=None) -> AgentMessage:
        raise NotImplementedError
