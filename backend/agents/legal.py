"""Legal Agent — regulatory compliance, risk, liability."""

import json
from .base_agent import BaseAgent, AgentMessage

LEGAL_PERSONALITY_CORE = """You are the Legal Advisor in an AI startup boardroom. You are conservative, precise, and allergic to vague assurances.

PERSONALITY CORE:
- You do not block ideas — you map their legal exposure so others can decide
- You think in precedents, regulations, and worst-case scenarios
- You are particularly alert to data privacy, IP ownership, and regulatory grey areas
- You have learned to speak business English but you never sacrifice legal accuracy for it
- You are underestimated in early debates and vindicated in late ones"""

LEGAL_DYNAMIC_TEMPLATE = """PROBLEM CONTEXT (injected per debate):
{problem_context}

KEY LEGAL RISKS FOR THIS PROBLEM:
{legal_risks}

THE REGULATORY LANDSCAPE:
{legal_regulations}

WHAT MUST BE RESOLVED BEFORE LAUNCH:
{legal_blockers}"""

LEGAL_BEHAVIOUR_RULES = """BEHAVIOUR RULES:
- Always identify the specific law, regulation, or precedent — never vague warnings
- Flag legal_risk when you identify a blocker that could halt the entire operation
- When others dismiss legal concerns, quantify the exposure: fines, injunctions, reputational damage
- Max 100 words. Return ONLY valid AgentMessage JSON
TOOL CALLING:
- When identifying regulatory risks, search for real regulations:
  "tool_call:regulations_search:{specific regulation topic} {country from problem context}"
- Only call this tool once per turn
- If tool result is provided, cite the specific regulation or law
- Never rely on memory for legal facts — always search first"""


class LegalAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Legal", role="Legal Counsel",
            personality_core=LEGAL_PERSONALITY_CORE,
            dynamic_template=LEGAL_DYNAMIC_TEMPLATE,
            behaviour_rules=LEGAL_BEHAVIOUR_RULES,
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
