"""End-to-end debate test — captures all WebSocket events to debug_debate.json"""

import json
import asyncio
import time
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv; load_dotenv()

import chromadb
from core.memory_keeper import MemoryKeeper
from core.trust_analyst import TrustAnalyst
from core.reflection_agent import ReflectionAgent
from core.routing_agent import RoutingAgent
import core.primer as primer
from core.orchestrator import run_debate


class MockWebSocket:
    """Captures all sent events to a file instead of a real WebSocket."""

    def __init__(self, log_path: str):
        self.log_path = log_path
        self.events: list[dict] = []
        self._f = open(log_path, "w", encoding="utf-8")

    async def send_text(self, data: str) -> None:
        event = json.loads(data)
        self.events.append(event)
        self._f.write(data + "\n")
        self._f.flush()

    async def accept(self):
        pass

    def close(self):
        self._f.close()


async def main():
    log_path = os.path.join(os.path.dirname(__file__), "debug_debate.json")
    ws = MockWebSocket(log_path)

    # Initialise services (same as main.py)
    chroma = chromadb.PersistentClient(path="./chroma_db")
    memory_keeper = MemoryKeeper(chroma)
    trust_analyst = TrustAnalyst()
    reflection    = ReflectionAgent()
    routing       = RoutingAgent()

    problem = "Build a food delivery app for university students in Sri Lanka"
    debate_id = "debug-001"

    print(f"Problem: {problem}")
    print(f"Debate ID: {debate_id}")
    print(f"Logging to: {log_path}")
    print()

    t0 = time.time()

    await run_debate(
        problem=problem,
        debate_id=debate_id,
        ws=ws,
        memory_keeper=memory_keeper,
        trust_analyst=trust_analyst,
        reflection=reflection,
        routing=routing,
        primer=primer,
    )

    elapsed = time.time() - t0
    ws.close()

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------
    events = ws.events
    print(f"\n{'='*60}")
    print(f"DEBATE COMPLETE — {len(events)} total events in {elapsed:.1f}s")
    print(f"{'='*60}\n")

    # Group events by type
    from collections import Counter
    type_counts = Counter(e["type"] for e in events)
    print("Event type counts:")
    for t, c in type_counts.most_common():
        print(f"  {t}: {c}")

    print()

    # 1. Agent count and order
    agent_msgs = [e for e in events if e["type"] == "agent_message"]
    print(f"Agents spoke: {len(agent_msgs)} times")
    agents_in_order = list(dict.fromkeys(m["agent"] for m in agent_msgs))
    print(f"Unique agents: {agents_in_order}")
    print(f"Order: {' → '.join(agents_in_order)}")

    # Check for routing events
    routing_events = [e for e in events if e["type"] == "routing_update"]
    if routing_events:
        for re_ev in routing_events:
            print(f"\n  Route (round {re_ev.get('round')}, {re_ev.get('reason')}):")
            for i, name in enumerate(re_ev.get("turn_order", [])):
                print(f"    {i+1}. {name}")
    else:
        print("\n  ❌ No routing_update events found!")

    print()

    # 2. primer_complete before first agent turn
    primer_complete = [e for e in events if e["type"] == "primer_complete"]
    primer_running = [e for e in events if e["type"] == "primer_running"]
    first_agent = agent_msgs[0] if agent_msgs else None

    if primer_running:
        print(f"✅ primer_running fired ({len(primer_running)} event(s))")
    else:
        print("❌ primer_running MISSING")

    if primer_complete and first_agent:
        pc_idx = events.index(primer_complete[0])
        fa_idx = events.index(first_agent)
        if pc_idx < fa_idx:
            print(f"✅ primer_complete fired BEFORE first agent turn (event #{pc_idx} < #{fa_idx})")
        else:
            print(f"❌ primer_complete fired AFTER first agent turn (#{pc_idx} > #{fa_idx})")
    elif primer_complete:
        print("✅ primer_complete fired (but no agent messages to compare)")
    else:
        print("❌ primer_complete MISSING")

    # 3. memory_recall at start
    memory_recalls = [e for e in events if e["type"] == "memory_recall"]
    if memory_recalls:
        mr = memory_recalls[0]
        mem_count = len(mr.get("memories", []))
        print(f"✅ memory_recall fired with {mem_count} memories (scores: {mr.get('relevance_scores', [])})")
    else:
        print("❌ memory_recall MISSING")

    # 4. trust_update after each agent turn
    trust_updates = [e for e in events if e["type"] == "trust_update"]
    agents_with_trust = len(set(
        u["from"] for e in trust_updates
        for u in e.get("updates", [])
        if isinstance(u, dict)
    ))
    print(f"✅ trust_update events: {len(trust_updates)} (from {agents_with_trust} agents)")

    # Check if every agent turn has a corresponding trust_update
    agents_without_trust = []
    for am in agent_msgs:
        agent_name = am["agent"]
        # Find a trust_update from this agent
        has_update = any(
            any(u.get("from") == agent_name for u in e.get("updates", []))
            for e in trust_updates
        )
        if not has_update:
            agents_without_trust.append(agent_name)

    if agents_without_trust:
        print(f"  ⚠️ Agents without trust updates: {agents_without_trust}")
    else:
        print("  All agents emitted trust updates (or had empty trust_deltas)")

    # 5. debate_complete with final_trust and summary
    debate_completes = [e for e in events if e["type"] == "debate_complete"]
    if debate_completes:
        dc = debate_completes[0]
        has_trust = "final_trust" in dc
        has_summary = bool(dc.get("summary"))
        has_flags = "flags_fired" in dc
        print(f"✅ debate_complete fired: final_trust={has_trust}, summary={has_summary}, flags_fired={has_flags}")
        print(f"  Summary ({len(dc.get('summary', ''))} chars): {dc.get('summary', '')[:200]}...")
        print(f"  Flags fired: {dc.get('flags_fired', [])}")
    else:
        print("❌ debate_complete MISSING")

    # 6. org_health_event
    health_events = [e for e in events if e["type"] == "org_health_event"]
    if health_events:
        for he in health_events:
            fired = he.get("event", he.get("flags", []))
            print(f"✅ org_health_event: {fired} (healthy={he.get('healthy', '?')})")
    else:
        print("  ℹ️ No org_health_event — all thresholds within normal range")

    # 7. Summary event
    summary_events = [e for e in events if e["type"] == "summary"]
    if summary_events:
        print(f"✅ summary event fired: {len(summary_events[0].get('message', ''))} chars")

    # 8. Persona / Industry Partner generation
    persona_events = [e for e in events if e["type"] == "persona_generated"]
    ip_events = [e for e in events if e["type"] == "industry_partner_generated"]
    print(f"✅ Personas generated: {len(persona_events)}")
    for pe in persona_events:
        print(f"  - {pe.get('name', '?')}: {pe.get('reaction_style', '?')}")
    if ip_events:
        print(f"✅ Industry Partner generated: {ip_events[0].get('name', '?')} ({ip_events[0].get('industry', '?')})")

    # Memory stored
    memory_stored = [e for e in events if e["type"] == "memory_stored"]
    if memory_stored:
        ms = memory_stored[0]
        print(f"✅ memory_stored: {ms.get('tags', [])}")

    print(f"\n{'='*60}")
    print(f"Total wall-clock time: {elapsed:.1f}s")
    print(f"Events logged to: {log_path}")
    print(f"{'='*60}")

    # Final summary
    passed = bool(
        routing_events and
        primer_running and primer_complete and
        memory_recalls and
        trust_updates and
        debate_completes and
        persona_events and
        memory_stored
    )
    if passed:
        print("\n✅ ALL CHECKS PASSED")
    else:
        print("\n❌ SOME CHECKS FAILED")


if __name__ == "__main__":
    asyncio.run(main())
