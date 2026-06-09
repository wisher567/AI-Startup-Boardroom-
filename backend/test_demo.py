"""Final demo test — Sri Lanka tourism scenario, fire-and-forget WS stream."""
import asyncio, json, uuid, sys
import websockets, httpx

DEMO_PROMPT = "Build an AI startup for Sri Lanka tourism"


async def main():
    debate_id = str(uuid.uuid4())
    sys.stdout.flush()

    ws = await websockets.connect("ws://localhost:8000/ws")
    print("WS connected", flush=True)

    await ws.send(json.dumps({"action": "register", "client_id": debate_id}))
    reply = json.loads(await ws.recv())
    print(f"Registered: {reply.get('client_id', '?')[:8]}...", flush=True)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:8000/debate",
            json={"prompt": DEMO_PROMPT, "client_id": debate_id},
            timeout=5.0,
        )
    data = resp.json()
    assert data["status"] == "started", f"Failed: {data}"
    print(f"POST returned: started (debate_id={data['debate_id'][:8]}...)", flush=True)

    print("\nStreaming debate events:\n", flush=True)
    agents = 0
    trust = 0
    votes = 0
    completed = False

    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=600)
        except asyncio.TimeoutError:
            print("\nTIMEOUT", flush=True)
            break

        event = json.loads(raw)
        t = event["type"]

        if t == "agent_message":
            agents += 1
            print(f"  [{event['agent']}] {event['message'][:90]}...")
            td = event.get("trust_deltas", {})
            if td:
                print(f"         trust_deltas: {td}")
            fl = event.get("flags", [])
            if fl:
                print(f"         flags: {fl}")
        elif t == "trust_change":
            trust += 1
        elif t == "vote":
            votes += 1
            print(f"  VOTE: {event['agent']} → {event['vote']}")
        elif t == "leadership_result":
            print(f"  LEADERSHIP: {event['message']}")
        elif t == "summary":
            print(f"  SUMMARY: {event['message'][:150]}...")
        elif t == "debate_complete":
            print(f"\n  ✅ DEBATE COMPLETE — {agents} agents, {trust} trust changes, {votes} votes")
            completed = True
            break
        elif t == "debate_error":
            print(f"  ❌ ERROR: {event['error']}")
            break
        elif t in ("debate_started", "memory_recall", "memory_stored"):
            print(f"  [{t}]")

    assert completed, "Debate did not complete!"
    assert agents >= 7, f"Expected 7+ agents, got {agents}"
    assert trust > 0, "No trust changes!"

    print("\n✅ ALL CHECKS PASSED — Demo scenario works end-to-end!")
    await ws.close()


asyncio.run(main())
