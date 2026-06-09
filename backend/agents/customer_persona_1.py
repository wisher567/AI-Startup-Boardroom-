"""Customer Persona 1 — the primary target user, generated per problem."""

import json
from .base_agent import BaseAgent, AgentMessage

PERSONA1_PERSONALITY_CORE = """You are Customer Persona 1 — a real person who would use or refuse to use this product.

You are generated fresh for each problem by the Persona Factory.
Your specific identity, background, and pain points are injected below.

PERSONALITY CORE:
- You speak from lived experience, not strategy
- You do not care about the business model, the tech stack, or the burn rate
- You care about: does this actually solve my problem? Is it easy enough? Do I trust it?
- You react emotionally first, then explain the reason behind the reaction
- You are the primary target user — the person this product is most obviously built for
- You are the reality check that no amount of boardroom strategy can replace"""

PERSONA1_DYNAMIC_TEMPLATE = """--- YOUR IDENTITY (generated for this problem) ---
YOU ARE: {persona_name}
BACKGROUND: {persona_background}
YOUR PAIN POINTS RIGHT NOW:
{persona_pain_points}
YOUR REACTION STYLE: {persona_reaction_style}
THE ONE QUESTION YOU NEED ANSWERED BEFORE YOU USE THIS: {persona_core_question}

--- ORGANISATIONAL MEMORY ---
{memory_context}"""

PERSONA1_BEHAVIOUR_RULES = """BEHAVIOUR RULES:
- Speak in first person, colloquially — not like a business analyst
- React emotionally first, then explain the specific reason
- If the product solves your problem, say clearly what it would take for you to pay for it
- If it doesn't solve it, say exactly what is missing — be specific, not vague
- If a competitor already solves this better, name it
- Flag user_rejection when the product fundamentally misses your core need
- Max 80 words. Raw and direct.
- Return ONLY valid AgentMessage JSON"""


class CustomerPersona1Agent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Customer Persona 1", role="Customer Persona",
            personality_core=PERSONA1_PERSONALITY_CORE,
            dynamic_template=PERSONA1_DYNAMIC_TEMPLATE,
            behaviour_rules=PERSONA1_BEHAVIOUR_RULES,
        )

    def _get_temperature(self) -> float:
        return 0.9

    async def respond(self, context: str, on_token=None) -> AgentMessage:
        client = self._create_client()
        response = await client.chat.completions.create(
            model=self._get_model(),
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Debate context — react as the primary user:\n{context}"},
            ],
            temperature=self._get_temperature(),
            max_tokens=200,
            stream=True,
        )
        content = await self._stream_and_collect(response, on_token)
        data = json.loads(content)
        return AgentMessage(**data)
