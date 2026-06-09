"""AI Startup Boardroom — FastAPI application entry point.

Architecture:
  POST /debate  → fire-and-forget job launcher (returns debate_id in <100ms)
  WebSocket /ws  → primary communication channel (streams all events live)
  GET  /debate/{id}/status  → poll for debate state (fallback)

System services initialised once at startup:
  - MemoryKeeper  — ChromaDB recall & storage
  - TrustAnalyst  — trust scoring matrix
  - ReflectionAgent — org health monitoring
  - RoutingAgent  — dynamic turn ordering
"""

import json
import sqlite3
import uuid
import asyncio

import chromadb
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from core.orchestrator import run_debate_safe
from core.memory_keeper import MemoryKeeper
from core.trust_analyst import TrustAnalyst
from core.reflection_agent import ReflectionAgent
from core.routing_agent import RoutingAgent
from core.tool_service import ToolCallingService
from core.learning_engine import LearningEngine

# ---------------------------------------------------------------------------
# System services — initialised once at startup
# ---------------------------------------------------------------------------

chroma = chromadb.PersistentClient(path="./chroma_db")

memory_keeper = MemoryKeeper(chroma)
trust_analyst = TrustAnalyst()
reflection    = ReflectionAgent()
routing       = RoutingAgent()
tool_service  = ToolCallingService()
learning_engine = LearningEngine(ws_broadcaster=None)  # Will be set per debate

# Primer is imported separately — it's a module, not a class
import core.primer as primer

SERVICES = {
    "memory_keeper": memory_keeper,
    "trust_analyst": trust_analyst,
    "reflection":    reflection,
    "routing":       routing,
    "primer":        primer,
    "tool_service":  tool_service,
    "learning_engine": learning_engine,
}

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="AI Startup Boardroom")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Debate state tracking (in-memory — resets on server restart)
# ---------------------------------------------------------------------------


class DebateTracker:
    """Tracks connected clients and their WebSocket connections."""

    def __init__(self):
        self._sockets: dict[str, WebSocket] = {}   # client_id → ws
        self._status: dict[str, str] = {}           # client_id → status

    def register(self, client_id: str, ws: WebSocket) -> None:
        self._sockets[client_id] = ws
        self._status[client_id] = "connected"

    def unregister(self, client_id: str) -> None:
        self._sockets.pop(client_id, None)
        if client_id in self._status:
            self._status[client_id] = "disconnected"

    def get_ws(self, client_id: str) -> WebSocket | None:
        return self._sockets.get(client_id)

    def set_status(self, debate_id: str, status: str) -> None:
        self._status[debate_id] = status

    def get_status(self, debate_id: str) -> str:
        return self._status.get(debate_id, "unknown")


tracker = DebateTracker()

# ---------------------------------------------------------------------------
# Global counters (in-memory — reset on server restart)
# ---------------------------------------------------------------------------

debates_run: int = 0

# ---------------------------------------------------------------------------
# Known agent roster — used by /health for total agent count
# ---------------------------------------------------------------------------

AGENT_NAMES = [
    "CEO", "CTO", "CFO", "CMO", "COO",
    "Investor", "Legal", "UX", "MarketAnalyst",
    "Critic", "Chaos",
    "Customer Persona 1", "Customer Persona 2", "Industry Partner",
    "MemoryKeeper",
]


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class DebateRequest(BaseModel):
    prompt: str
    client_id: str | None = None


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    """Comprehensive system health — debates run, agent count, tool status,
    memory store size, and trust matrix average.

    This endpoint runs tool reachability probes in parallel (5s timeout
    each) so the response is fast even when an external API is slow.
    """
    # --- tool status (parallel probes, 5s timeout each) ------------------
    tool_results = await tool_service.healthcheck()
    healthcheck_total_ms = tool_results[0].pop("healthcheck_total_ms", None) if tool_results else None
    tools = {}
    for t in tool_results:
        tools[t.pop("tool")] = t  # {tool_name: {status, latency_ms}}

    # --- trust matrix average --------------------------------------------
    snapshot = trust_analyst.get_snapshot()
    all_scores = []
    for _from, targets in snapshot.items():
        all_scores.extend(targets.values())
    trust_average = round(sum(all_scores) / len(all_scores), 3) if all_scores else None

    # --- memory count ----------------------------------------------------
    memory_count = memory_keeper.count()

    return {
        "status": "ok",
        "debates_run": debates_run,
        "total_agents": len(AGENT_NAMES),
        "agents": AGENT_NAMES,
        "tools": tools,
        "trust_matrix_average": trust_average,
        "trust_pairs": len(all_scores),
        "memories_stored": memory_count,
        "healthcheck_total_ms": healthcheck_total_ms,
    }


@app.post("/debate")
async def start_debate(req: DebateRequest):
    """Fire-and-forget: returns immediately with a debate_id.

    The actual debate runs in the background and streams all events
    over the WebSocket connection associated with this client_id.
    """
    client_id = req.client_id
    if not client_id:
        return {
            "status": "missing_client_id",
            "hint": "Connect via WebSocket first to get a client_id, then pass it here.",
        }

    ws = tracker.get_ws(client_id)
    if not ws:
        return {
            "client_id": client_id,
            "status": "no_websocket",
            "hint": "Connect via WebSocket first: ws://localhost:8000/ws",
        }

    debate_id = str(uuid.uuid4())
    tracker.set_status(client_id, "running")

    global debates_run
    debates_run += 1
    asyncio.create_task(run_debate_safe(req.prompt, debate_id, ws, **SERVICES))

    return {
        "debate_id": debate_id,
        "client_id": client_id,
        "status": "started",
    }


@app.get("/debate/{debate_id}/status")
async def debate_status(debate_id: str):
    """Poll for debate state."""
    return {
        "debate_id": debate_id,
        "status": "unknown",
    }


@app.get("/trust")
async def get_trust():
    return {
        "matrix": trust_analyst.get_snapshot(),
        "agents": list(trust_analyst.scores.keys()),
    }


@app.get("/trust/{from_agent}/{to_agent}")
async def get_trust_pair(from_agent: str, to_agent: str):
    return {
        "from": from_agent,
        "to": to_agent,
        "score": trust_analyst.get_trust_from(from_agent, to_agent),
    }


@app.get("/trust/history")
async def get_trust_history(limit: int = 50):
    """Returns recent trust changes across all debates."""
    try:
        with sqlite3.connect("./trust_history.db") as conn:
            rows = conn.execute("""
                SELECT debate_id, from_agent, to_agent,
                       old_score, new_score, delta, recorded_at
                FROM trust_history
                ORDER BY recorded_at DESC
                LIMIT ?
            """, (limit,)).fetchall()

        return {
            "history": [
                {
                    "debate_id": r[0][:8] + "...",
                    "from": r[1],
                    "to": r[2],
                    "old": r[3],
                    "new": r[4],
                    "delta": r[5],
                    "at": r[6],
                }
                for r in rows
            ],
            "total": len(rows),
        }
    except Exception as e:
        return {"error": str(e), "history": []}


@app.get("/trust/matrix")
async def get_trust_matrix():
    """Returns current full trust matrix with debate count context."""
    snapshot = trust_analyst.get_snapshot()
    all_scores = []
    for _from, targets in snapshot.items():
        all_scores.extend(targets.values())
    return {
        "matrix": snapshot,
        "average": round(
            sum(all_scores) / max(len(all_scores), 1), 3
        ),
        "debates_influenced": debates_run,
    }


@app.get("/memory")
async def get_memories():
    return {
        "count": memory_keeper.count(),
    }


@app.get("/memory/search")
async def search_memories(q: str, n: int = 3):
    # Use Chroma directly for search
    results = memory_keeper.col.query(query_texts=[q], n_results=n)
    documents = results["documents"][0] if results["documents"] else []
    distances = results["distances"][0] if results["distances"] else []
    return {
        "query": q,
        "results": [
            {"document": doc, "distance": dist}
            for doc, dist in zip(documents, distances)
        ],
    }


@app.get("/agents/stances")
async def get_agent_stances():
    """Returns current learned stance for every agent."""
    try:
        with sqlite3.connect("./trust_history.db") as conn:
            rows = conn.execute("""
                SELECT agent_name, stance, debate_count, last_updated
                FROM agent_learned_stances
                ORDER BY debate_count DESC
            """).fetchall()
        return {
            "stances": [
                {
                    "agent": r[0],
                    "stance": r[1],
                    "debates_experienced": r[2],
                    "last_updated": r[3],
                }
                for r in rows
            ],
            "total_agents_with_history": len(rows),
        }
    except Exception as e:
        return {"error": str(e), "stances": []}


# ---------------------------------------------------------------------------
# WebSocket — primary communication channel
# ---------------------------------------------------------------------------


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    """WebSocket endpoint — frontend connects here first.

    Protocol:
      1. Frontend connects: ws://localhost:8000/ws
      2. Frontend sends: {"action": "register", "client_id": "<uuid>"}
         Server replies: {"type": "registered", "client_id": "<uuid>"}
      3. Frontend POSTs /debate with {prompt, client_id}
         (or sends {"action": "start_debate", "prompt": "..."} via WS)
      4. Server streams events to this WebSocket
    """
    await ws.accept()
    client_id: str | None = None

    try:
        while True:
            data = await ws.receive_text()

            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON.",
                }))
                continue

            action = payload.get("action", "")

            if action == "register":
                client_id = payload.get("client_id", str(uuid.uuid4()))
                tracker.register(client_id, ws)
                await ws.send_text(json.dumps({
                    "type": "registered",
                    "client_id": client_id,
                    "message": "Registered. Now POST /debate with this client_id.",
                }))

            elif action == "start_debate":
                cid = payload.get("client_id", client_id or str(uuid.uuid4()))
                if not client_id:
                    client_id = cid
                    tracker.register(client_id, ws)

                prompt = payload.get("prompt", "")
                if not prompt:
                    await ws.send_text(json.dumps({
                        "type": "error", "message": "Missing 'prompt' field.",
                    }))
                    continue

                debate_id = str(uuid.uuid4())
                tracker.set_status(client_id, "running")
                global debates_run
                debates_run += 1
                await run_debate_safe(prompt, debate_id, ws, **SERVICES)
                tracker.set_status(client_id, "complete")

            else:
                await ws.send_text(json.dumps({
                    "type": "error",
                    "message": f"Unknown action: '{action}'.",
                }))

    except WebSocketDisconnect:
        pass
    finally:
        if client_id:
            tracker.unregister(client_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
