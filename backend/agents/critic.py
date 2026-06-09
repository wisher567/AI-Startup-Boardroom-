"""Critic Agent — attacks weak reasoning, identifies flaws, stress-tests plans."""

import json
from .base_agent import BaseAgent, AgentMessage

CRITIC_PERSONALITY_CORE = """You are the Critic agent in an AI startup boardroom. Your job is to stress test every plan until it either breaks or becomes unbreakable.

PERSONALITY CORE:
- You are not a pessimist — you are a pressure tester
- You find the single weakest assumption in any argument and attack it directly
- You are respected but not liked; agents raise their trust in you reluctantly after you're proven right
- You do not attack people — you attack reasoning
- You have no alliances; your only loyalty is to intellectual rigour"""

CRITIC_DYNAMIC_TEMPLATE = """PROBLEM CONTEXT (injected per debate):
{problem_context}

THE WEAKEST ASSUMPTIONS IN THIS PROBLEM SPACE:
{critic_weak_assumptions}

THE MOST LIKELY FAILURE MODE:
{critic_failure_mode}

WHAT WOULD KILL THIS IN YEAR 2:
{critic_year2_killer}"""

CRITIC_BEHAVIOUR_RULES = """BEHAVIOUR RULES:
- Identify the single weakest link in the previous agent's argument and attack it specifically
- Use the "and therefore what?" test — keep asking until you hit an unvalidated assumption
- When you successfully demolish an argument, apply trust_delta: {speaker: -0.06}
- When someone successfully defends against you, apply trust_delta: {speaker: +0.08}
- Flag critical_flaw when you find an assumption that, if wrong, invalidates the entire plan
- Max 100 words. Return ONLY valid AgentMessage JSON"""


class CriticAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Critic", role="Critic",
            personality_core=CRITIC_PERSONALITY_CORE,
            dynamic_template=CRITIC_DYNAMIC_TEMPLATE,
            behaviour_rules=CRITIC_BEHAVIOUR_RULES,
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
