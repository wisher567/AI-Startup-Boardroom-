"""Quick memory engine integration test."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from core.memory_engine import memory_engine
from core.orchestrator import run_debate


async def main():
    prompt1 = "Build an AI app for meditation and mindfulness"

    print(f"Memory count before: {memory_engine.count()}")

    # Run a debate — this stores a memory afterwards
    print(f"\nRunning debate on: {prompt1}")
    events = await run_debate(prompt1)

    # Find the memory_stored event
    for e in events:
        if e["type"] == "memory_stored":
            print(f"\nMemory stored! ID: {e['debate_id']}")
            print(f"Memory: {e['memory'][:150]}...")
            print(f"Tags: {e['tags']}")
        elif e["type"] == "memory_recall":
            print(f"Memory recall: {e['memories_found']} memories (total: {e['total_stored']})")

    print(f"\nMemory count after: {memory_engine.count()}")

    # Run second debate — should recall the first
    prompt2 = "Build a wellness tourism startup"
    print(f"\nRunning second debate on: {prompt2}")
    events2 = await run_debate(prompt2)

    for e in events2:
        if e["type"] == "memory_recall":
            print(f"Memory recall: {e['memories_found']} memories (total: {e['total_stored']})")
        elif e["type"] == "memory_stored":
            print(f"Memory stored! ID: {e['debate_id']}")

    print(f"\nFinal memory count: {memory_engine.count()}")

    # Test search
    results = memory_engine.recall("meditation mindfulness wellness", n=2)
    print(f"\nSearch results for 'meditation mindfulness wellness':")
    for r in results:
        print(f"  - {r['document'][:100]}... (distance: {r['distance']:.3f})")


if __name__ == "__main__":
    asyncio.run(main())
