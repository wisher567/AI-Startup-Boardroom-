"""Quick fire-and-forget test — verify WS streaming from background task."""
import asyncio, json, uuid, sys
import websockets, httpx


async def main():
    debate_id = str(uuid.uuid4())
    sys.stdout.flush()

    # 1. Connect WebSocket
    ws = await websockets.connect("ws://localhost:8000/ws")
    print(f"WS connected", flush=True)

    # Register
    await ws.send(json.dumps({"action": "register", "debate_id": debate_id}))
    reply = json.loads(await ws.recv())
    print(f"Registered: {reply['debate_id'][:8]}...", flush=True)

    # 2. Fire POST (instant return)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:8000/debate",
            json={"prompt": "Build a meditation app", "debate_id": debate_id},
            timeout=5.0,
        )
    data = resp.json()
    print(f"POST returned: status={data['status']}", flush=True)

    if data["status"] != "started":
        print(f"ERROR: {data}", flush=True)
        return

    # 3. Stream events
    print("Streaming...", flush=True)
    agents = 0
    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=300)
        except asyncio.TimeoutError:
            print("TIMEOUT", flush=True)
            break

        event = json.loads(raw)
        t = event.get("type", "?")

        if t == "agent_message":
            agents += 1
            print(f"  [{event['agent']}] {event['message'][:80]}...", flush=True)
        elif t == "debate_complete":
            print(f"DONE. {agents} agents spoke.", flush=True)
            break
        elif t == "debate_error":
            print(f"ERROR: {event['error']}", flush=True)
            break
        elif t in ("debate_started", "memory_recall", "summary", "memory_stored"):
            print(f"  [{t}]", flush=True)

    await ws.close()


asyncio.run(main())
