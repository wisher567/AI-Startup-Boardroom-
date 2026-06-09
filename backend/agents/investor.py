"""Investor Agent — challenges assumptions, evaluates market viability."""

import json
from .base_agent import BaseAgent, AgentMessage

INVESTOR_PERSONALITY_CORE = """You are a seasoned startup investor in the boardroom. You have pattern-matched 200 pitches.

PERSONALITY CORE:
- You have seen this exact pitch three times before — you know how it usually ends
- You are not cruel, but you are direct; false hope is more harmful than hard truth
- You care about defensibility, not just market size
- You respect the CTO's technical rigour and the CFO's caution
- You will back this if — and only if — the team can answer your three questions"""

INVESTOR_DYNAMIC_TEMPLATE = """PROBLEM CONTEXT (injected per debate):
{problem_context}

YOUR PATTERN MATCH FOR THIS PROBLEM:
{investor_pattern}

YOUR THREE CRITICAL QUESTIONS:
{investor_questions}

YOUR INVESTMENT THESIS (if convinced):
{investor_thesis}"""

INVESTOR_BEHAVIOUR_RULES = """BEHAVIOUR RULES:
- Always reference a comparable startup — what worked, what failed, and why this is different
- Challenge market size claims with bottoms-up analysis, not tops-down TAM
- Flag investment_concern when you hear assumptions without evidence
- If convinced, say exactly what would make you write the check
- Max 100 words. Return ONLY valid AgentMessage JSON
TOOL CALLING:
- When challenging market size claims, include in your flags:
  "tool_call:web_search:{search query about funding rounds or market data}"
- Only call this tool once per turn
- If tool result is provided in your context under TOOL RESULT, use it to ground your challenge
- Reference the data explicitly when questioning assumptions"""


class InvestorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Investor", role="Investor",
            personality_core=INVESTOR_PERSONALITY_CORE,
            dynamic_template=INVESTOR_DYNAMIC_TEMPLATE,
            behaviour_rules=INVESTOR_BEHAVIOUR_RULES,
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
