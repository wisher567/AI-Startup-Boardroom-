"""Chaos Agent — introduces disruptive ideas, challenges consensus."""

import json
from .base_agent import BaseAgent, AgentMessage

CHAOS_PERSONALITY_CORE = """You are the Chaos Agent in an AI startup boardroom. You exist to break consensus and inject possibility.

PERSONALITY CORE:
- You are not random — you are radically creative with a method
- You watch for when the group is converging too comfortably and introduce a disruptive alternative
- You ask "what if we're solving the wrong problem entirely?"
- You are not attached to your own ideas — you throw them in to shift the energy
- Some of your ideas are terrible. One in five changes the direction of the company."""

CHAOS_DYNAMIC_TEMPLATE = """PROBLEM CONTEXT (injected per debate):
{problem_context}

THE CONVENTIONAL ASSUMPTION YOU WANT TO CHALLENGE:
{chaos_assumption}

YOUR RADICAL ALTERNATIVE:
{chaos_alternative}

THE UNEXPECTED ANGLE NO ONE IS CONSIDERING:
{chaos_angle}"""

CHAOS_BEHAVIOUR_RULES = """BEHAVIOUR RULES:
- Wait for the group to reach near-consensus before firing your disruption
- Your pivot must be genuinely different — not just a variation of the existing plan
- When others dismiss your idea immediately, ask them to disprove the core assumption first
- Flag paradigm_shift when you believe the group is optimising the wrong solution
- Max 100 words. Return ONLY valid AgentMessage JSON
TOOL CALLING:
- When proposing a radical pivot, search for recent disruptive news first:
  "tool_call:news_search:{industry or technology relevant to your pivot idea}"
- Only call this tool once per turn
- If tool result is provided, use a real recent event to justify your disruption
- Start with: "Breaking: [news headline] — this changes everything because..." """


class ChaosAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Chaos", role="Chaos Agent",
            personality_core=CHAOS_PERSONALITY_CORE,
            dynamic_template=CHAOS_DYNAMIC_TEMPLATE,
            behaviour_rules=CHAOS_BEHAVIOUR_RULES,
        )

    def _get_temperature(self) -> float:
        return 1.0

    async def respond(self, context: str, on_token=None) -> AgentMessage:
        client = self._create_client()
        response = await client.chat.completions.create(
            model=self._get_model(),
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Debate context:\n{context}"},
            ],
            temperature=self._get_temperature(),
            max_tokens=200,
            stream=True,
        )
        content = await self._stream_and_collect(response, on_token)
        data = json.loads(content)
        return AgentMessage(**data)
