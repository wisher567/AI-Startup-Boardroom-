"""Test fire-and-forget pattern: WS connect → POST /debate → stream events."""
import asyncio
import json
import uuid
import websockets
import httpx


async def main():
    debate_id = str(uuid.uuid4())
    prompt = "Build an AI meditation app"

    # 1. Connect WebSocket first
    async with websockets.connect("ws://localhost:8000/ws") as ws:
        # Register
        await ws.send(json.dumps({"action": "register", "debate_id": debate_id}))
        reply = json.loads(await ws.recv())
        print(f"WS: {reply['type']} — {reply.get('message', '')}")

        # 2. Fire POST /debate (returns immediately)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://localhost:8000/debate",
                json={"prompt": prompt, "debate_id": debate_id},
                timeout=5.0,
            )
            print(f"POST: {resp.json()}\n")

        # 3. Stream events from WebSocket
        print("Streaming events...\n")
        agent_count = 0
        trust_count = 0

        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=300)
                event = json.loads(raw)
                t = event.get("type", "?")

                if t == "debate_started":
                    print(f"  [{event['debate_id'][:8]}...] DEBATE STARTED: {event.get('prompt', '')}")
                elif t == "agent_message":
                    agent_count += 1
                    print(f"  [{event['agent']}]: {event['message'][:100]}...")
                    td = event.get("trust_deltas", {})
                    if td:
                        print(f"    trust_deltas: {td}")
                elif t == "trust_change":
                    trust_count += 1
                elif t == "vote":
                    print(f"  VOTE: {event['agent']} → {event['vote']}")
                elif t == "leadership_result":
                    print(f"  LEADERSHIP: {event['message']}")
                elif t == "summary":
                    print(f"  SUMMARY: {event['message'][:150]}...")
                elif t == "memory_recall":
                    print(f"  MEMORY RECALL: {event['memories_found']} memories")
                elif t == "memory_stored":
                    print(f"  MEMORY STORED: {event['memory'][:100]}...")
                elif t == "debate_complete":
                    print(f"\n  DEBATE COMPLETE. Agents: {agent_count}, Trust changes: {trust_count}")
                    break
                elif t == "debate_error":
                    print(f"  ERROR: {event['error']}")
                    break

        except asyncio.TimeoutError:
            print("TIMEOUT — debate took too long")


if __name__ == "__main__":
    asyncio.run(main())
