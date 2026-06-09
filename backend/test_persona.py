"""Quick test: persona generation only."""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from agents.persona_factory import generate_personas


async def main():
    prompt = "Build an AI startup for Sri Lanka tourism"
    print(f"Generating personas for: {prompt}\n", flush=True)

    personas = await generate_personas(prompt)
    print(f"Got {len(personas)} personas:\n", flush=True)

    for p in personas:
        print(f"  Name: {p.name}")
        print(f"  Background: {p.background}")
        print(f"  Pain points: {p.pain_points}")
        print(f"  Style: {p.reaction_style}")
        print()


asyncio.run(main())
