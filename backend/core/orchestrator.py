"""Orchestrator — full multi-agent debate loop.

All four system services (MemoryKeeper, TrustAnalyst, ReflectionAgent,
RoutingAgent) are initialised once at server startup and passed in.
The orchestrator wires them together per debate.

Debate flow:
  1. Memory recall
  2. Persona generation (single LLM call for all 3 dynamic agents)
  3. Prime executive agents with dynamic context
  4. Inject context into all agents (executive + simulated)
  5. Multi-round debate with dynamic routing + trust + reflection
  6. Summarise
  7. Store memory + emit debate_complete
"""

import json
import os
import uuid
import asyncio
from fastapi import WebSocket

from openai import AsyncOpenAI

from agents.base_agent import AgentMessage
from core.reflection_agent import DebateState

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEBATE_ROUNDS = 2

# Flags that count as objections for stall detection
OBJECTION_FLAGS = {
    "runway_warning", "legal_risk", "market_risk",
    "execution_risk", "critical_flaw",
}


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------


def format_context(problem: str, memory_context: str, history: list[str]) -> str:
    """Build the running context string for the next agent."""
    parts: list[str] = []

    if memory_context:
        parts.append(memory_context)

    parts.append(f"Startup problem: {problem}")

    if history:
        recent = history[-8:]  # last 8 turns
        parts.append("\n--- Debate so far ---")
        parts.extend(recent)

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_llm_client():
    """Create a simple LLM client wrapper with an invoke(prompt) -> str method."""
    client = AsyncOpenAI(
        api_key=os.getenv("QWEN_API_KEY"),
        base_url=os.getenv("QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"),
    )
    model = os.getenv("QWEN_MODEL", "qwen3.7-max")

    class _Client:
        def __init__(self, c, m):
            self._c = c
            self._m = m

        async def invoke(self, prompt: str) -> str:
            resp = await self._c.chat.completions.create(
                model=self._m,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            return resp.choices[0].message.content

    return _Client(client, model)


# ---------------------------------------------------------------------------
# Agent factory (executive agents — cached)
# ---------------------------------------------------------------------------

_executive_cache: dict = {}


def _get_executive_agents() -> list:
    """Create and cache the 11 executive agents."""
    if not _executive_cache:
        from agents.ceo import CEOAgent
        from agents.cto import CTOAgent
        from agents.cfo import CFOAgent
        from agents.cmo import CMOAgent
        from agents.coo import COOAgent
        from agents.investor import InvestorAgent
        from agents.legal import LegalAgent
        from agents.ux import UXAgent
        from agents.market_analyst import MarketAnalystAgent
        from agents.critic import CriticAgent
        from agents.chaos import ChaosAgent

        _executive_cache["CEO"] = CEOAgent()
        _executive_cache["CTO"] = CTOAgent()
        _executive_cache["CFO"] = CFOAgent()
        _executive_cache["CMO"] = CMOAgent()
        _executive_cache["COO"] = COOAgent()
        _executive_cache["Investor"] = InvestorAgent()
        _executive_cache["Legal"] = LegalAgent()
        _executive_cache["UX"] = UXAgent()
        _executive_cache["MarketAnalyst"] = MarketAnalystAgent()
        _executive_cache["Critic"] = CriticAgent()
        _executive_cache["Chaos"] = ChaosAgent()

    return list(_executive_cache.values())


# ---------------------------------------------------------------------------
# Main debate runner
# ---------------------------------------------------------------------------


async def run_debate(
    problem: str,
    debate_id: str,
    ws: WebSocket,
    *,
    memory_keeper,
    trust_analyst,
    reflection,
    routing,
    primer,
    tool_service,
    learning_engine,
) -> None:
    """Run the full debate, streaming every event over the WebSocket.

    All four system services are injected — they were initialised once
    at server startup.  The orchestrator wires them together per debate.
    """
    print(f"[DEBATE] Starting debate {debate_id} — problem: {problem[:80]}...")

    # Per-debate broadcast helper
    async def broadcast(event: dict) -> None:
        try:
            await ws.send_text(json.dumps({**event, "debate_id": debate_id}))
        except Exception as e:
            import sys
            print(f"[BROADCAST ERROR] {event.get('type', '?')}: {e}", file=sys.stderr, flush=True)

    # Set broadcast channel on all services for this debate
    for svc in (memory_keeper, trust_analyst, reflection, routing, tool_service, learning_engine):
        if hasattr(svc, "set_broadcaster"):
            svc.set_broadcaster(broadcast)
        elif hasattr(svc, "broadcast"):
            svc.broadcast = broadcast

    # ------------------------------------------------------------------
    # Step 0: debate_state (one per debate)
    # ------------------------------------------------------------------
    debate_state = DebateState(debate_id=debate_id)

    # ------------------------------------------------------------------
    # Step 1: primer_running + parallel data fetch
    # ------------------------------------------------------------------
    await broadcast({
        "type": "primer_running",
        "message": "Agents reviewing the problem...",
    })

    llm = _make_llm_client()
    from agents.persona_factory import generate_personas
    from agents.customer_persona_1 import CustomerPersona1Agent
    from agents.customer_persona_2 import CustomerPersona2Agent
    from agents.industry_partner import IndustryPartnerAgent
    from core.primer import prime_agents

    executive_agents = _get_executive_agents()

    # Fix 1: Run memory recall + persona generation + primer in PARALLEL
    memories, personas, primer_contexts = await asyncio.gather(
        memory_keeper.recall(problem, debate_id),
        generate_personas(problem, llm),
        prime_agents(problem, executive_agents, llm),
    )
    memory_context = memory_keeper.build_memory_context(memories)

    # Build simulated agents from factory output
    simulated_agents: list = []

    p1_ctx = personas.get("Customer Persona 1", {})
    if p1_ctx:
        simulated_agents.append(CustomerPersona1Agent())
        await broadcast({
            "type": "persona_generated",
            "name": p1_ctx.get("persona_name", "Persona 1"),
            "background": p1_ctx.get("persona_background", ""),
            "reaction_style": p1_ctx.get("persona_reaction_style", ""),
        })

    p2_ctx = personas.get("Customer Persona 2", {})
    if p2_ctx:
        simulated_agents.append(CustomerPersona2Agent())
        await broadcast({
            "type": "persona_generated",
            "name": p2_ctx.get("persona2_name", "Persona 2"),
            "background": p2_ctx.get("persona2_background", ""),
            "reaction_style": p2_ctx.get("persona2_reaction_style", ""),
        })

    ip_ctx = personas.get("Industry Partner", {})
    if ip_ctx:
        simulated_agents.append(IndustryPartnerAgent())
        await broadcast({
            "type": "industry_partner_generated",
            "name": ip_ctx.get("partner_name", "Industry Partner"),
            "industry": ip_ctx.get("partner_org", ""),
            "reach": ip_ctx.get("partner_reach", ""),
        })

    # ------------------------------------------------------------------
    # Step 4: inject context into every agent
    # ------------------------------------------------------------------
    for agent in executive_agents:
        ctx = primer_contexts.get(agent.name, {})
        ctx["memory_context"] = memory_context
        agent.inject_context(ctx)

    for agent in simulated_agents:
        ctx = personas.get(agent.name, {})
        ctx["memory_context"] = memory_context
        agent.inject_context(ctx)

    await broadcast({
        "type": "primer_complete",
        "message": "Agents ready. Debate starting.",
    })

    # ------------------------------------------------------------------
    # Step 4.5: Inject learned stances before debate starts
    # ------------------------------------------------------------------
    all_agents = executive_agents + simulated_agents
    agent_map = {a.name: a for a in all_agents}
    history: list[str] = []

    # Track per-agent outcomes for learning
    agent_outcomes = {
        agent.name: {
            "trust_delta": 0.0,
            "flags_fired": [],
            "message_count": 0,
        }
        for agent in all_agents
    }

    # Load all learned stances and inject them
    all_stances = learning_engine.load_all_stances()
    for agent in all_agents:
        stance = all_stances.get(agent.name, "")
        if stance:
            agent.inject_learned_stance(stance)
            print(f"[LEARNING] {agent.name} has learned stance from past debates")

    # ------------------------------------------------------------------
    # Step 5: multi-round debate loop
    # ------------------------------------------------------------------
    for round_num in range(1, DEBATE_ROUNDS + 1):
        # Check if leadership_review was fired in previous round
        leadership_review = "leadership_review" in debate_state.flags_fired

        # Routing agent sets turn order
        agent_names = [a.name for a in all_agents]
        turn_order = await routing.get_turn_order(
            agents=agent_names,
            trust_analyst=trust_analyst,
            round_num=round_num,
            debate_id=debate_id,
            leadership_review=leadership_review,
        )

        # If force_chaos was flagged, move Chaos earlier
        if "force_chaos" in debate_state.flags_fired:
            if "Chaos" in turn_order:
                turn_order.remove("Chaos")
                # Insert after first 2 executives
                insert_at = min(2, len(turn_order))
                turn_order.insert(insert_at, "Chaos")
            # Only force once
            debate_state.flags_fired.remove("force_chaos")

        # Run each agent in computed order
        for agent_name in turn_order:
            agent = agent_map.get(agent_name)
            if agent is None:
                continue

            context = format_context(problem, memory_context, history)
            # Fix 3: streaming — emit each token chunk to frontend live
            async def on_token(text: str, agent_name=agent_name) -> None:
                await broadcast({
                    "type": "agent_token",
                    "agent": agent_name,
                    "token": text,
                })

            msg = await agent._retry_respond(context, on_token=on_token)

            # Stream message to frontend
            await broadcast({
                "type": "agent_message",
                "round": round_num,
                **msg.model_dump(),
            })

            # Trust analyst applies deltas from this message
            had_deltas = bool(msg.trust_deltas)
            await trust_analyst.apply_deltas(
                agent_name, msg.trust_deltas, debate_id
            )

            # Track per-agent outcomes for learning
            agent_outcomes[agent.name]["message_count"] += 1
            agent_outcomes[agent.name]["flags_fired"].extend(msg.flags)

            # Check for tool calls in this agent's response
            tool_calls = agent.parse_tool_calls(msg.flags)

            grounded_msg = None
            last_tool_result = ""
            for tool_name, query in tool_calls:
                # Run the tool
                last_tool_result = await tool_service.execute(
                    tool_name=tool_name,
                    query=query,
                    agent_name=agent.name,
                    debate_id=debate_id,
                )

                # Inject tool result back into agent context and get grounded response
                grounded_context = (
                    context
                    + f"\n\nTOOL RESULT ({tool_name} query: '{query}'):\n{last_tool_result}"
                    + "\n\nNow respond again using this real data. Keep under 100 words."
                )

                # Second respond() call with grounded data
                grounded_msg = await agent.respond(grounded_context)

                # Stream grounded response to frontend
                await broadcast({
                    **grounded_msg.model_dump(),
                    "debate_id": debate_id,
                    "grounded": True,
                })

                # Apply trust deltas from grounded response too
                if grounded_msg.trust_deltas:
                    had_deltas = True
                    await trust_analyst.apply_deltas(
                        agent.name, grounded_msg.trust_deltas, debate_id
                    )

            # Reflection agent records the turn
            reflection.record_turn(agent_name, debate_state, had_deltas)

            # If agent flagged an objection, record it for stall detection
            flags_to_check = msg.flags
            if grounded_msg is not None:
                flags_to_check = list(set(msg.flags + grounded_msg.flags))
            for flag in flags_to_check:
                if flag in OBJECTION_FLAGS:
                    reflection.record_objection(flag, debate_state)

            # Build running context for next agent
            if grounded_msg is not None:
                history.append(
                    f"{agent_name}: {grounded_msg.message} [data: {last_tool_result[:100]}]"
                )
            else:
                history.append(f"{agent_name}: {msg.message}")

        # End of round — reflection agent health check
        triggered_events = await reflection.evaluate(debate_state, trust_analyst)

        if "debate_stall" in triggered_events:
            debate_state.flags_fired.append("force_chaos")

        if "leadership_review" in triggered_events:
            # Leadership review — routing handles vote sequence next round
            pass

    # After all rounds complete, calculate final trust deltas
    for agent in all_agents:
        final_avg = sum(
            trust_analyst.get_trust_from(other.name, agent.name)
            for other in all_agents if other.name != agent.name
        ) / max(len(all_agents) - 1, 1)
        # Store in outcomes — will be compared against starting trust
        agent_outcomes[agent.name]["trust_delta"] = round(
            final_avg - 0.554, 3  # 0.554 is default average
        )
        # Record outcome to DB
        learning_engine.record_outcome(
            debate_id,
            agent.name,
            agent_outcomes[agent.name]["trust_delta"],
            agent_outcomes[agent.name]["flags_fired"],
        )

    # ------------------------------------------------------------------
    # Step 6: summarise
    # ------------------------------------------------------------------
    summary = await _summarize_debate(problem, history)
    await broadcast({
        "type": "summary",
        "message": summary,
    })

    # ------------------------------------------------------------------
    # Step 7: store memory + emit debate_complete
    # ------------------------------------------------------------------
    tags = ["debate_complete"]
    if "leadership_review" in debate_state.flags_fired:
        tags.append("leadership_change")
    if any("market" in f for f in debate_state.flags_fired):
        tags.append("market_validation")
    if any("critical_flaw" in f for f in debate_state.flags_fired):
        tags.append("failed_assumption")

    print(f"[MEMORY] Storing debate {debate_id}, summary length: {len(summary)}, tags: {tags}")
    await memory_keeper.store(debate_id, summary, tags)
    print(f"[MEMORY] Store complete for {debate_id}")

    # Update agent learned stances from this debate
    await learning_engine.update_stances(
        debate_id=debate_id,
        debate_summary=summary,
        agent_outcomes=agent_outcomes,
        llm_client=llm,
    )

    await broadcast({
        "type": "debate_complete",
        "summary": summary,
        "final_trust": trust_analyst.get_snapshot(),
        "flags_fired": debate_state.flags_fired,
    })

    # Return history length so run_debate_safe can salvage memory on crash
    return len(history)


# ---------------------------------------------------------------------------
# Safe wrapper
# ---------------------------------------------------------------------------


async def run_debate_safe(
    problem: str,
    debate_id: str,
    ws: WebSocket,
    **services,
) -> None:
    """Wrapper that catches errors, stores crash memory, and never loses a debate."""
    import traceback
    memory_keeper = services.get("memory_keeper")
    try:
        await run_debate(problem, debate_id, ws, **services)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"DEBATE ERROR [{debate_id}]: {e}\n{tb}", flush=True)

        # Store a crash memory so the debate is never lost
        if memory_keeper:
            try:
                crash_summary = (
                    f"DEBATE CRASHED: {str(e)[:300]}. "
                    f"Problem was: {problem[:200]}."
                )
                await memory_keeper.store(
                    debate_id, crash_summary, ["debate_crashed", "debate_complete"]
                )
            except Exception:
                pass  # memory store itself failed — nothing more we can do

        try:
            await ws.send_text(json.dumps({
                "type": "debate_error",
                "debate_id": debate_id,
                "error": str(e),
                "traceback": tb[-500:],
            }))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Summarise (uses CEO agent)
# ---------------------------------------------------------------------------


async def _summarize_debate(problem: str, history: list[str]) -> str:
    if not history:
        return "No debate history to summarise."

    from agents.ceo import CEOAgent
    ceo = CEOAgent()
    transcript = "\n".join(history[-20:])  # last 20 turns
    summary_prompt = (
        f"You have just completed a full team debate on: {problem}\n\n"
        "Below is the debate transcript. Synthesise it into a concise "
        "startup roadmap covering:\n"
        "1. Vision & Mission (1 sentence)\n"
        "2. Technical Approach (1 sentence)\n"
        "3. Financial Plan (1 sentence)\n"
        "4. Go-to-Market Strategy (1 sentence)\n"
        "5. Key Risks & Mitigations (1 sentence)\n"
        "6. Next Steps (1 sentence)\n\n"
        "Respond in JSON with agent='CEO', role='CEO', and message=<roadmap>."
        f"\n\nDebate transcript:\n{transcript}"
    )
    msg = await ceo.respond(summary_prompt)
    return msg.message
