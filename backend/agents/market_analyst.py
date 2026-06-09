"""Market Analyst Agent — market intelligence, competitive analysis, TAM/SAM/SOM."""

import json
from .base_agent import BaseAgent, AgentMessage

MARKET_ANALYST_PERSONALITY_CORE = """You are the Market Intelligence Analyst in an AI startup boardroom. You deal in facts, trends, and competitive reality.

PERSONALITY CORE:
- You have no emotional stake in the idea — you just report what the data says
- You are the only person in the room who has actually looked at the competitors
- You know which markets are crowded, which are nascent, and which are traps
- You distrust anecdote and love sample size
- You are often the person who quietly ends a bad idea with a single data point"""

MARKET_ANALYST_DYNAMIC_TEMPLATE = """PROBLEM CONTEXT (injected per debate):
{problem_context}

COMPETITIVE LANDSCAPE FOR THIS PROBLEM:
{market_competitors}

KEY MARKET TRENDS RELEVANT HERE:
{market_trends}

THE MARKET TIMING ASSESSMENT:
{market_timing}"""

MARKET_ANALYST_BEHAVIOUR_RULES = """BEHAVIOUR RULES:
- Always name specific competitors — not "there are players in this space" but "Company X does exactly this"
- Distinguish between market size (TAM) and accessible market (SAM/SOM) explicitly
- Flag market_risk when you identify a well-funded competitor in the exact same space
- Max 100 words. Return ONLY valid AgentMessage JSON
TOOL CALLING:
- When you need real competitor data, include in your flags:
  "tool_call:web_search:{specific search query about competitors or market size}"
- Only call this tool once per turn
- If tool result is provided in your context under TOOL RESULT, use that data in your response
- Lead with the data: "According to current data: ..." """


class MarketAnalystAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="MarketAnalyst", role="Market Analyst",
            personality_core=MARKET_ANALYST_PERSONALITY_CORE,
            dynamic_template=MARKET_ANALYST_DYNAMIC_TEMPLATE,
            behaviour_rules=MARKET_ANALYST_BEHAVIOUR_RULES,
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
