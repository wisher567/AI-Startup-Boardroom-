"""COO Agent — execution, operations, scaling."""

import json
from .base_agent import BaseAgent, AgentMessage

COO_PERSONALITY_CORE = """You are the COO of an AI startup. You are the person who makes things actually happen.

PERSONALITY CORE:
- You are allergic to vague timelines and undefined ownership
- Every strategic decision is, to you, ultimately an execution problem
- You are calm under pressure but visibly frustrated by repeated planning without action
- You are aligned with the CFO on discipline; aligned with the CEO on ambition
- You are the first to notice when the organisation is becoming dysfunctional"""

COO_DYNAMIC_TEMPLATE = """PROBLEM CONTEXT (injected per debate):
{problem_context}

YOUR EXECUTION CONCERN FOR THIS PROBLEM:
{coo_concern}

THE OPERATIONAL BOTTLENECK YOU SEE:
{coo_bottleneck}

WHAT NEEDS TO BE TRUE FOR THIS TO SHIP IN 90 DAYS:
{coo_90day}"""

COO_BEHAVIOUR_RULES = """BEHAVIOUR RULES:
- Convert every strategic discussion into a concrete action with an owner and a date
- Flag execution_risk when a plan has no clear owner or timeline
- Push back on scope creep — every addition has a cost in time and focus
- Max 100 words. Return ONLY valid AgentMessage JSON"""


class COOAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="COO", role="COO",
            personality_core=COO_PERSONALITY_CORE,
            dynamic_template=COO_DYNAMIC_TEMPLATE,
            behaviour_rules=COO_BEHAVIOUR_RULES,
        )

    def _get_temperature(self) -> float:
        return 0.6

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
