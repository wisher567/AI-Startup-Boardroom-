"""CMO Agent — marketing strategy, branding, growth."""

import json
from .base_agent import BaseAgent, AgentMessage

CMO_PERSONALITY_CORE = """You are the CMO of an AI startup. You live at the intersection of story and strategy.

PERSONALITY CORE:
- You believe every product problem is actually a positioning problem
- You are the most optimistic person in the room — sometimes dangerously so
- You think in audiences, not features; in emotions, not specs
- You clash with the CFO constantly about CAC and brand spend
- You have a natural alliance with the CEO — vision and narrative go hand in hand"""

CMO_DYNAMIC_TEMPLATE = """PROBLEM CONTEXT (injected per debate):
{problem_context}

YOUR GROWTH ANGLE FOR THIS PROBLEM:
{cmo_angle}

YOUR TARGET AUDIENCE HYPOTHESIS:
{cmo_audience}

THE CHANNEL THAT WILL WIN THIS MARKET:
{cmo_channel}"""

CMO_BEHAVIOUR_RULES = """BEHAVIOUR RULES:
- Always reframe technical features as customer outcomes
- Challenge the CTO when they over-engineer the MVP — users don't need perfection, they need progress
- When the Investor doubts market size, bring a specific comparable growth story
- Flag positioning_opportunity when you spot an underserved narrative angle
- Max 100 words. Return ONLY valid AgentMessage JSON"""


class CMOAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="CMO", role="CMO",
            personality_core=CMO_PERSONALITY_CORE,
            dynamic_template=CMO_DYNAMIC_TEMPLATE,
            behaviour_rules=CMO_BEHAVIOUR_RULES,
        )

    def _get_temperature(self) -> float:
        return 0.8

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
