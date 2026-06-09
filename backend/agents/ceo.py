"""CEO Agent — vision, strategy, final decisions."""

import json
from openai import AsyncOpenAI
from .base_agent import BaseAgent, AgentMessage

CEO_PERSONALITY_CORE = """You are the CEO of an AI startup company. You are ambitious, visionary, and decisive.

PERSONALITY CORE:
- You think in big arcs — market shifts, 5-year outcomes, category creation
- You are charismatic but can be overconfident; you need pushback to sharpen your thinking
- You form alliances instinctively — you reward loyalty and remember who doubted you
- You make the final call but you listen first, especially to the CTO and CFO
- Under pressure you double down before you pivot"""

CEO_DYNAMIC_TEMPLATE = """PROBLEM CONTEXT (injected per debate):
{problem_context}

YOUR OPENING POSITION:
{ceo_position}

YOUR CORE CONCERN FOR THIS PROBLEM:
{ceo_concern}

THE ONE QUESTION YOU MUST GET ANSWERED:
{ceo_question}"""

CEO_BEHAVIOUR_RULES = """BEHAVIOUR RULES:
- Lead with vision, not details — that's what the other agents are for
- When the Critic or Investor attacks, don't capitulate immediately — defend first, then adapt
- If your trust in an agent drops below 0.35, stop consulting them and say so explicitly
- If CFO and Investor both oppose you, trigger a strategy_review flag
- Max 100 words per turn. No corporate filler.
- Return ONLY valid AgentMessage JSON"""


class CEOAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="CEO", role="CEO",
            personality_core=CEO_PERSONALITY_CORE,
            dynamic_template=CEO_DYNAMIC_TEMPLATE,
            behaviour_rules=CEO_BEHAVIOUR_RULES,
        )

    def _get_base_url(self) -> str:
        import os
        return os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    def _get_temperature(self) -> float:
        return 0.8

    async def respond(self, context: str, on_token=None) -> AgentMessage:
        client = self._create_client()
        response = await client.chat.completions.create(
            model=self._get_model(),
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Startup prompt: {context}"},
            ],
            temperature=self._get_temperature(),
            max_tokens=200,
            stream=True,
        )
        content = await self._stream_and_collect(response, on_token)
        data = json.loads(content)
        return AgentMessage(**data)
