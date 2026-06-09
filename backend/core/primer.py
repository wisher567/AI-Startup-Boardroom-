"""Primer — generates dynamic context for every agent before a debate.

Runs once per debate. Takes the user's problem statement, calls the LLM,
and fills every agent's dynamic placeholders (e.g. {ceo_position},
{ceo_concern}, {ceo_question} for the CEO).

Each agent defines its own placeholder keys via get_placeholder_keys() /
get_spec_for_primer(). The primer reads these dynamically so new agents
or renamed placeholders work without touching the primer.

Emits primer_running / primer_complete WebSocket events so the frontend
can show "Agents reviewing the problem..."
"""

import json

# ---------------------------------------------------------------------------
# Primer prompt — built dynamically from each agent's placeholder keys
# ---------------------------------------------------------------------------


def _build_primer_system_prompt(agents: list) -> str:
    """Build a primer system prompt that tells the LLM exactly which keys to
    generate for each agent, by reading get_placeholder_keys() from every agent.

    Produces instructions like:
      CEO: problem_context, ceo_position, ceo_concern, ceo_question
      CTO: problem_context, cto_position, cto_concern, cto_question
      ...
    """
    specs = [a.get_spec_for_primer() for a in agents]

    return (
        "You are the Debate Primer — a meta-intelligence that prepares agents "
        "for a startup boardroom debate.\n\n"
        "Given a problem statement, you generate personalised dynamic context "
        "for each agent. This context shapes how each agent approaches the debate.\n\n"
        "For EACH agent listed below, produce exactly the fields shown:\n\n"
        + "\n".join(f"  {s}" for s in specs)
        + "\n\n"
        "Guidelines:\n"
        "- problem_context: The problem reframed through THIS agent's specific lens "
        "(1-2 sentences). Make it provocative for them.\n"
        "- *_position: This agent's likely opening position or stance (1 sentence). "
        "What they naturally default to.\n"
        "- *_concern: This agent's single deepest worry or fear about this specific "
        "problem (1 sentence). What keeps them up at night.\n"
        "- *_question: The ONE question this agent must get answered before they "
        "can commit (1 sentence). Sharp and specific.\n\n"
        "Be opinionated. Give each agent a genuinely different perspective — if "
        "two agents sound the same you've failed. Draw out natural tensions "
        "(e.g. CTO wants to build, CFO wants to conserve cash; CEO wants to "
        "move fast, Legal wants to slow down).\n\n"
        "Return valid JSON with an \"agents\" key mapping agent names to their "
        "field dicts. Each dict MUST use the exact field names shown above — "
        "no aliases, no renames."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def prime_agents(
    problem: str,
    agents: list,
    llm_client,
) -> dict[str, dict[str, str]]:
    """Generate dynamic context for every 3-layer agent.

    Does NOT inject — the orchestrator handles injection so it can add
    memory_context and persona data alongside the primer output.

    Args:
        problem: The user's startup problem statement.
        agents: List of BaseAgent instances.
        llm_client: Async client with invoke(prompt: str) -> str method.

    Returns:
        Dict mapping agent name → context dict ready for inject_context().
    """
    # Only prime agents that use the 3-layer prompt architecture
    # AND haven't already been primed (e.g. by the Persona Factory)
    dynamic_agents = [
        a for a in agents
        if a.has_dynamic_context() and not a.dynamic_context
    ]
    if not dynamic_agents:
        return {}

    system_prompt = _build_primer_system_prompt(dynamic_agents)

    raw = await llm_client.invoke(system_prompt + f"\n\nProblem: {problem}")
    data = json.loads(raw)
    return data.get("agents", {})
