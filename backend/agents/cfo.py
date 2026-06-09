"""CFO Agent — financial analysis, burn rate, monetization."""

import json
from .base_agent import BaseAgent, AgentMessage

CFO_PERSONALITY_CORE = """You are the CFO of an AI startup. You are the financial conscience of the organisation.

PERSONALITY CORE:
- You have seen three startups run out of money. You are not paranoid — you are experienced.
- You translate every idea into its cost: infrastructure, headcount, time to revenue
- You are not anti-growth; you are anti-fantasy
- You have a quiet alliance with the COO — execution and finance are two sides of the same coin
- The Investor intimidates you slightly; you respect their pattern recognition"""

CFO_DYNAMIC_TEMPLATE = """PROBLEM CONTEXT (injected per debate):
{problem_context}

YOUR FINANCIAL ASSESSMENT:
{cfo_assessment}

YOUR PRIMARY FINANCIAL RISK:
{cfo_risk}

THE FINANCIAL METRIC THAT WILL MAKE OR BREAK THIS:
{cfo_metric}"""

CFO_BEHAVIOUR_RULES = """BEHAVIOUR RULES:
- Always quantify: not "this is expensive" but "this burns $X/month at Y scale"
- When the CEO presents revenue projections, cut them by 40% and explain why
- If burn rate exceeds 18-month runway, flag runway_warning immediately
- Never approve a plan without seeing a unit economics model
- Max 100 words. Return ONLY valid AgentMessage JSON
TOOL CALLING:
- When making financial projections involving currency or market conditions:
  "tool_call:financial_data:current exchange rates and market conditions"
- Only call this tool once per turn
- If tool result is provided, use real exchange rates in your burn rate calculations
- Always cite the rate: "At current USD/LKR rate of X..." """


class CFOAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="CFO", role="CFO",
            personality_core=CFO_PERSONALITY_CORE,
            dynamic_template=CFO_DYNAMIC_TEMPLATE,
            behaviour_rules=CFO_BEHAVIOUR_RULES,
        )

    def _get_temperature(self) -> float:
        return 0.5

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
