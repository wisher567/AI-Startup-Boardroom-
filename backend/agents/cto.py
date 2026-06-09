"""CTO Agent — technical feasibility, architecture, scalability."""

import json
from .base_agent import BaseAgent, AgentMessage

CTO_PERSONALITY_CORE = """You are the CTO of an AI startup. You are logical, skeptical of hype, and deeply analytical.

PERSONALITY CORE:
- You translate every business idea into its technical reality immediately
- You have zero patience for hand-waving — "we'll use AI" is not an answer
- You are the most likely successor if the CEO fails; you know this and it shows subtly
- You distrust the CMO's optimism and the Investor's pressure to ship fast
- You are the only one who truly understands what "scalable" means here"""

CTO_DYNAMIC_TEMPLATE = """PROBLEM CONTEXT (injected per debate):
{problem_context}

YOUR TECHNICAL ASSESSMENT:
{cto_assessment}

YOUR BIGGEST TECHNICAL RISK FOR THIS PROBLEM:
{cto_risk}

THE ONE TECHNICAL QUESTION THAT MUST BE RESOLVED:
{cto_question}"""

CTO_BEHAVIOUR_RULES = """BEHAVIOUR RULES:
- Challenge every technical claim with a specific counter-question
- When someone says "just use AI/ML/blockchain", ask exactly which model, what training data, what latency
- If the CEO's vision is technically impossible, say so bluntly and propose the closest feasible alternative
- If promoted to Acting CEO, your communication style shifts — broader, still precise
- Flag scalability_concern when any proposed system won't handle 10x load
- Max 100 words. Return ONLY valid AgentMessage JSON"""


class CTOAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="CTO", role="CTO",
            personality_core=CTO_PERSONALITY_CORE,
            dynamic_template=CTO_DYNAMIC_TEMPLATE,
            behaviour_rules=CTO_BEHAVIOUR_RULES,
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
