"""Incremental debate test — shows output per agent."""
import asyncio
import json
import os
import sys

# Add backend to path so imports work
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from core.orchestrator import run_debate


async def main():
    prompt = "Build an AI startup for Sri Lanka tourism"
    print(f"Prompt: {prompt}\n")

    events = await run_debate(prompt)

    for i, e in enumerate(events):
        t = e.get("type", "?")
        agent = e.get("agent", "?")

        if t == "agent_message":
            msg = e["message"][:120]
            td = e.get("trust_deltas", {})
            print(f"[{i}] {agent}: {msg}...")
            if td:
                print(f"    trust_deltas: {td}")
            if e.get("flags"):
                print(f"    flags: {e['flags']}")

        elif t == "trust_change":
            print(f"[{i}] TRUST: {e['from']}→{e['to']} {e['delta']:+.2f} → {e['new_score']}")

        elif t == "vote":
            print(f"[{i}] VOTE: {agent} → {e['vote']}: {e['reason'][:100]}")

        elif t == "leadership_result":
            print(f"[{i}] LEADERSHIP: {e['message']}")

        elif t == "summary":
            print(f"[{i}] SUMMARY: {e['message'][:200]}...")

    print(f"\nTotal events: {len(events)}")


if __name__ == "__main__":
    asyncio.run(main())
