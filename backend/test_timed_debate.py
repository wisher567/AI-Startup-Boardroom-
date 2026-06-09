"""Timed debate test — measures wall-clock time and tracks per-agent metrics."""
import asyncio
import json
import uuid
import time
import sys
import websockets
import httpx


AGENTS_EXPECTED = {
    "CEO", "CTO", "CFO", "CMO", "COO",
    "Investor", "Legal", "UX", "MarketAnalyst",
    "Critic", "Chaos",
    "Customer Persona 1", "Customer Persona 2",
    "Industry Partner",
}

PROMPT = "Build a food delivery app for university students in Sri Lanka"


async def main():
    debate_id = str(uuid.uuid4())

    # --- Per-agent counters ---
    agent_tokens: dict[str, int] = {}        # agent_name → token count
    agent_messages: dict[str, int] = {}       # agent_name → message count
    agent_retries: dict[str, int] = {}        # agent_name → retry count
    all_events: list[dict] = []

    start_wall = time.perf_counter()

    async with websockets.connect("ws://localhost:8000/ws", ping_interval=None) as ws:
        # Register
        await ws.send(json.dumps({"action": "register", "client_id": debate_id}))
        reply = json.loads(await ws.recv())
        print(f"Registered: {reply.get('type')} — {reply.get('client_id', '')[:12]}...")

        # Fire debate (POST returns immediately)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://localhost:8000/debate",
                json={"prompt": PROMPT, "client_id": debate_id},
                timeout=10.0,
            )
            post_data = resp.json()
            print(f"POST /debate → {post_data.get('status')}, debate_id={post_data.get('debate_id', '?')[:12]}...\n")

        if post_data.get("status") != "started":
            print(f"ERROR: Debate did not start. Response: {post_data}")
            return

        # Stream events
        print("Streaming events...\n")
        debate_started = False
        debate_ended = False

        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=600)
                event = json.loads(raw)
                t = event.get("type", "?")
                all_events.append(event)

                if t == "debate_started":
                    debate_started = True
                    print(f"[{event['debate_id'][:8]}...] DEBATE STARTED: {event.get('prompt', '')}")

                elif t == "agent_token":
                    agent = event.get("agent", "?")
                    agent_tokens[agent] = agent_tokens.get(agent, 0) + 1

                elif t == "agent_message":
                    agent = event.get("agent", "?")
                    agent_messages[agent] = agent_messages.get(agent, 0) + 1
                    td = event.get("trust_deltas", {})
                    fl = event.get("flags", [])
                    summary = f"[{agent}] round={event.get('round','?')} msg_len={len(event.get('message',''))}"
                    if td:
                        summary += f" trust_deltas={td}"
                    if fl:
                        summary += f" flags={fl}"
                    print(summary)

                elif t == "agent_retry":
                    agent = event.get("agent", "?")
                    agent_retries[agent] = agent_retries.get(agent, 0) + 1
                    print(f"[{agent}] RETRY triggered (attempt {event.get('attempt','?')})")

                elif t == "primer_complete":
                    print(f"PRIMER COMPLETE. Debate rounds starting...")

                elif t == "routing_update":
                    print(f"ROUTING round {event.get('round','?')}: {event.get('turn_order',[])}")

                elif t == "trust_update":
                    pass  # skip verbose trust dumps

                elif t == "summary":
                    print(f"SUMMARY: {event.get('message', '')[:200]}...")

                elif t == "debug_retry":
                    agent = event.get("agent", "?")
                    agent_retries[agent] = agent_retries.get(agent, 0) + 1
                    print(f"[{agent}] DEBUG RETRY: attempt={event.get('attempt','?')} error={event.get('error','?')[:80]}")

                elif t == "debate_complete":
                    debate_ended = True
                    end_wall = time.perf_counter()
                    break

                elif t == "debate_error":
                    print(f"ERROR: {event.get('error','?')}")
                    end_wall = time.perf_counter()
                    break

        except asyncio.TimeoutError:
            print("TIMEOUT — debate took too long")
            end_wall = time.perf_counter()

    # --- Report ---
    wall_ms = (end_wall - start_wall) * 1000
    wall_s = wall_ms / 1000

    print("\n" + "=" * 70)
    print("  DEBATE RESULTS")
    print("=" * 70)
    print(f"  Prompt:          {PROMPT}")
    print(f"  Wall-clock time: {wall_s:.2f}s ({wall_ms:.0f}ms)")
    print(f"  Total events:    {len(all_events)}")
    print()

    # Agent token summary
    print(f"  {'Agent':<22s} {'Tokens':>8s} {'Msgs':>6s} {'Retries':>8s}")
    print(f"  {'-'*22} {'-'*8} {'-'*6} {'-'*8}")
    total_tokens = 0
    total_msgs = 0
    total_retries = 0
    for agent_name in sorted(AGENTS_EXPECTED):
        t = agent_tokens.get(agent_name, 0)
        m = agent_messages.get(agent_name, 0)
        r = agent_retries.get(agent_name, 0)
        total_tokens += t
        total_msgs += m
        total_retries += r
        print(f"  {agent_name:<22s} {t:>8d} {m:>6d} {r:>8d}")

    print(f"  {'-'*22} {'-'*8} {'-'*6} {'-'*8}")
    print(f"  {'TOTAL':<22s} {total_tokens:>8d} {total_msgs:>6d} {total_retries:>8d}")
    print()

    # Final answers
    agents_seen_tokens = set(agent_tokens.keys())
    agents_seen_msgs = set(agent_messages.keys())
    all_agents_active = agents_seen_tokens == AGENTS_EXPECTED
    all_agents_messaged = agents_seen_msgs == AGENTS_EXPECTED

    print(f"  All {len(AGENTS_EXPECTED)} agents had agent_token events: {'YES' if all_agents_active else 'NO'}")
    if not all_agents_active:
        missing = AGENTS_EXPECTED - agents_seen_tokens
        print(f"    Missing tokens: {missing}")
        extra = agents_seen_tokens - AGENTS_EXPECTED
        if extra:
            print(f"    Extra: {extra}")

    print(f"  All {len(AGENTS_EXPECTED)} agents had agent_message events: {'YES' if all_agents_messaged else 'NO'}")
    if not all_agents_messaged:
        missing = AGENTS_EXPECTED - agents_seen_msgs
        print(f"    Missing messages: {missing}")

    print(f"  Debate completed: {'YES' if debate_ended else 'NO'}")
    print(f"  Total retries triggered: {total_retries}")
    print(f"  Retry-free run: {'YES' if total_retries == 0 else 'NO — retries detected'}")

    print()
    print("=" * 70)
    print(f"  WALL TIME: {wall_s:.2f}s")
    print(f"  AGENT_TOKENS: {total_tokens} events across {len(agents_seen_tokens)} agents")
    print(f"  RETRIES: {total_retries}")
    print(f"  ALL 14 COMPLETED: {'YES' if (all_agents_messaged and debate_ended and total_retries == 0) else 'NO'}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
