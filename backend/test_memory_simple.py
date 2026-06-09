"""Minimal memory engine test — save + recall only, no LLM calls."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from core.memory_engine import memory_engine

# Test save
print(f"Count before save: {memory_engine.count()}")

memory_engine.save(
    summary="Meditation AI startup: CEO lost leadership vote 6-1 after investor challenged CAC assumptions.",
    metadata={"prompt": "Build an AI app for meditation", "tags": "meditation, wellness, leadership_fail"},
)
memory_engine.save(
    summary="Sri Lanka tourism: pivoted to B2B hotel DMC model. CTO flagged integration risks with cash vendors.",
    metadata={"prompt": "Build an AI startup for Sri Lanka tourism", "tags": "tourism, sri_lanka, b2b, pivot"},
)

print(f"Count after save: {memory_engine.count()}")

# Test recall
results = memory_engine.recall("wellness tourism startup asia", n=2)
print(f"\nRecall 'wellness tourism startup asia':")
for r in results:
    print(f"  [{r['distance']:.3f}] {r['document'][:120]}")

# Test format_context
ctx = memory_engine.format_context("Build a travel app for southeast asia")
print(f"\nFormat context:\n{ctx[:300]}")

# Test get_recent
print("\nRecent memories:")
for r in memory_engine.get_recent(5):
    print(f"  - {r['document'][:100]}")
    print(f"    tags: {r['metadata'].get('tags', 'N/A')}")

print("\nDone!")
