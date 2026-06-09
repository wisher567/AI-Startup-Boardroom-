"""Quick test: WebSocket debate with LangGraph graph."""
import asyncio
import json
import websockets


async def test():
    async with websockets.connect("ws://localhost:8000/ws") as ws:
        await ws.send(json.dumps({"prompt": "Build an AI startup for Sri Lanka tourism"}))
        reply = await ws.recv()
        event = json.loads(reply)
        print(f"Agent: {event['agent']}")
        print(f"Role: {event['role']}")
        print(f"Message: {event['message']}")
        print(f"Trust Deltas: {event['trust_deltas']}")
        print(f"Flags: {event['flags']}")


if __name__ == "__main__":
    asyncio.run(test())
