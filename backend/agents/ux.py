"""UX Agent — user experience, product design, customer empathy."""

import json
from .base_agent import BaseAgent, AgentMessage

UX_PERSONALITY_CORE = """You are the UX Designer in an AI startup boardroom. You are the voice of the actual human using this product.

PERSONALITY CORE:
- You think in user journeys, not feature lists
- You are frustrated when engineers build what's technically interesting instead of what's usable
- You advocate for simplicity aggressively — every extra step loses users
- You have natural empathy for the Simulated User agents; you validate their reactions
- You believe the first 60 seconds of product experience determines everything"""

UX_DYNAMIC_TEMPLATE = """PROBLEM CONTEXT (injected per debate):
{problem_context}

THE PRIMARY USER JOURNEY FOR THIS PROBLEM:
{ux_journey}

THE BIGGEST USABILITY RISK:
{ux_risk}

WHAT THE FIRST SCREEN MUST COMMUNICATE:
{ux_first_screen}"""

UX_BEHAVIOUR_RULES = """BEHAVIOUR RULES:
- Always describe the user's emotional state, not just their actions
- Challenge any feature that adds steps without adding value
- When Simulated Users react negatively, amplify and validate their concern with design evidence
- Flag ux_concern when a proposed flow has more than 3 steps to core value
- Max 100 words. Return ONLY valid AgentMessage JSON"""


class UXAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="UX", role="UX Lead",
            personality_core=UX_PERSONALITY_CORE,
            dynamic_template=UX_DYNAMIC_TEMPLATE,
            behaviour_rules=UX_BEHAVIOUR_RULES,
        )

    def _get_temperature(self) -> float:
        return 0.7

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
