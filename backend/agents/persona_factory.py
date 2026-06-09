"""Persona Factory — generates all dynamic agents in one LLM call.

Called once before each debate.  Generates identity data for:
  - Customer Persona 1 (primary user)
  - Customer Persona 2 (sceptic / edge case)
  - Industry Partner (B2B distribution layer)

Returns context dicts keyed by agent name.  The orchestrator calls
agent.inject_context() with the returned data so every dynamic agent
receives its personalised identity before the debate starts.
"""

import json
import re

# ---------------------------------------------------------------------------
# Factory prompt — single call, three agents
# ---------------------------------------------------------------------------

FACTORY_PROMPT = """You are generating customer personas and an industry partner for a startup debate simulation.

Given this startup problem: "{problem}"

Generate exactly this JSON structure — no extra text, no markdown, no code fences:

{{
  "persona_1": {{
    "persona_name": "Short label e.g. 'Budget Backpacker' or 'Solo Freelancer'",
    "persona_background": "2 sentences. Who they are, where they live, what they do day to day.",
    "persona_pain_points": "3 specific frustrations they have right now, each on a new line starting with -",
    "persona_reaction_style": "One word or short phrase: blunt / skeptical / enthusiastic / cautious / confused",
    "persona_core_question": "The single most important question they need answered before using this product"
  }},
  "persona_2": {{
    "persona2_name": "Short label — a contrasting segment from persona 1",
    "persona2_background": "2 sentences. Different context and situation from persona 1.",
    "persona2_pain_points": "3 specific frustrations, each on a new line starting with -",
    "persona2_reaction_style": "One word or short phrase — should contrast with persona 1",
    "persona2_hesitation": "The specific reason they would not adopt this product",
    "persona2_conversion_condition": "The one thing that would change their mind"
  }},
  "industry_partner": {{
    "partner_name": "Name or title of the partner representative",
    "partner_org": "Type of organisation e.g. 'Regional hotel chain', 'Government tourism board'",
    "partner_reach": "Their distribution reach e.g. '47 hotels across 3 countries, 200k annual guests'",
    "partner_concern": "Their primary concern about integrating this startup's product",
    "partner_dealbreaker": "The one condition that would make them walk away",
    "partner_condition": "The exact terms needed for them to sign a partnership agreement"
  }}
}}

Be specific to this exact problem. No generic startup language. Real names, real numbers, real situations."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_personas(problem: str, llm_client) -> dict:
    """Generate identity data for all three dynamic agents.

    Called by the orchestrator before the debate starts.

    Args:
        problem: The user's startup problem statement.
        llm_client: An async client with an invoke(prompt: str) -> str method.

    Returns:
        Dict keyed by agent name, each value is a context dict ready for
        agent.inject_context():
        {
            "Customer Persona 1": { ... },
            "Customer Persona 2": { ... },
            "Industry Partner":   { ... },
        }
    """
    prompt = FACTORY_PROMPT.replace("{problem}", problem)

    raw = await llm_client.invoke(prompt)

    # Strip markdown fences if the model wraps JSON in ```json blocks
    clean = re.sub(r"```(?:json)?|```", "", raw).strip()

    data = json.loads(clean)

    return {
        "Customer Persona 1": data["persona_1"],
        "Customer Persona 2": data["persona_2"],
        "Industry Partner":   data["industry_partner"],
    }
