# AI Startup Boardroom

> A multi-agent debate simulation where 15 AI personas with competing agendas, a dynamic trust graph, and live MCP tool integrations stress-test your startup idea — so you don't have to hire a $50K advisory board.

---

## The Problem

Early-stage founders cannot afford a real advisory board. Lawyers charge $500/hour. Seasoned investors won't take your call. Market analysts need retainers. So founders rely on gut feel, a few mentor conversations, and generic single-perspective LLM chat — which gives you the answer you want to hear, not the one you need.

**Generic LLM chat fails founders because:**
- One model, one perspective — no pushback, no competing agendas
- No memory of past debates — repeats the same advice
- No trust dynamics — can't simulate the real politics of a boardroom
- No real-world data grounding — hallucinates market sizes and competitor names
- No emergent behaviour — can't surprise you with insights you didn't ask for

---

## What Makes This Different

### Dynamic Trust Graph
Every agent has a trust score toward every other agent (55 initialised pairs). Trust shifts in real time based on debate outcomes — the CEO loses credibility when the Critic demolishes their argument, the CFO gains influence when their runway warning proves correct. **Emergent leadership changes** happen when CEO trust drops below 0.40 from 3+ agents — the board votes in an Acting CEO.

### Emergent Leadership
The system doesn't script "CEO is in charge." If the CEO's trust collapses, the ReflectionAgent triggers a `leadership_review` — the board votes, and the CTO or CFO can become Acting CEO mid-debate. The RoutingAgent reorders turn sequence accordingly.

### 15-Agent Society
11 executive agents (CEO through Chaos), 3 dynamically generated user personas (Persona Factory creates fresh identities per problem), and 1 silent system agent (MemoryKeeper). Each has a unique personality, alliances, biases, and communication style — and they remember past debates via ChromaDB vector memory.

### Live MCP Tool Calls
5 agents can call real-world APIs mid-debate: the Market Analyst searches for actual competitors, the CFO fetches live exchange rates, the Chaos Agent surfaces breaking news to justify pivots. Tool results are injected back into the agent's context for a grounded second response.

### Persona Factory
Instead of hardcoded user personas, a single LLM call generates three fresh identities per problem — a primary user, a sceptic, and an industry partner. Their backgrounds, pain points, and reaction styles are tailored to the specific startup problem, so every debate gets custom user validation.

### Institutional Memory
The organisation accumulates institutional memory across debates — trust relationships persist in SQLite, strategic outcomes in ChromaDB. A returning problem gets debated by agents who already have opinions about each other.

---

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full Mermaid diagram and event flow.

```
User → POST /debate → Orchestrator → 7-step pipeline:
  1. Memory Recall (ChromaDB)
  2. Persona Factory (3 dynamic agents)
  3. Primer (per-agent context injection)
  4. Debate Loop (2 rounds × dynamic routing × trust scoring × tool calls)
  5. Summarise (CEO agent synthesises roadmap)
  6. Store Memory (compressed to ChromaDB)
  → WebSocket stream → React + Phaser frontend (live)
```

---

## Agent Society

| # | Agent | Role | Type | Unique Behaviour |
|---|---|---|---|---|
| 1 | **CEO** | CEO | Executive | Visionary leader; doubles down before pivoting; triggers `strategy_review` |
| 2 | **CTO** | CTO | Executive | Technical sceptic; "what model, what data, what latency?"; can become Acting CEO |
| 3 | **CFO** | CFO | Executive | Financial conscience; cuts revenue projections by 40%; calls `runway_warning` |
| 4 | **CMO** | CMO | Executive | Eternal optimist; reframes features as outcomes; calls `positioning_opportunity` |
| 5 | **COO** | COO | Executive | Execution realist; converts strategy to owners + dates; calls `execution_risk` |
| 6 | **Investor** | Investor | Executive | Pattern-matched 200 pitches; challenges with bottoms-up analysis; calls `investment_concern` |
| 7 | **Legal** | Legal Counsel | Executive | Precise legal mind; never vague — always cites specific law; calls `legal_risk` |
| 8 | **UX** | UX Lead | Executive | User empathy champion; thinks in journeys not features; calls `ux_concern` |
| 9 | **MarketAnalyst** | Market Analyst | Executive | Data-driven realist; names specific competitors; calls `market_risk` |
| 10 | **Critic** | Critic | Executive | Pressure tester; attacks weakest assumption; calls `critical_flaw` |
| 11 | **Chaos** | Chaos Agent | Executive | Consensus breaker; 1 in 5 ideas changes direction; calls `paradigm_shift` |
| 12 | **Customer Persona 1** | Customer Persona | User (dynamic) | Primary target user; reacts emotionally; calls `user_rejection` |
| 13 | **Customer Persona 2** | Customer Persona | User (dynamic) | Sceptical edge case; "I almost use it but don't"; calls `user_hesitation` |
| 14 | **Industry Partner** | Industry Partner | User (dynamic) | B2B distribution gatekeeper; asks for SLA and rev share; calls `partnership_condition` |
| 15 | **MemoryKeeper** | Memory Keeper | System (silent) | Never speaks; compresses debates to 300-char memories; retrieves past context |

---

## MCP Tool Integrations

| Tool | Used By | Data Source | What It Adds |
|---|---|---|---|
| **web_search** | MarketAnalyst, Investor | DuckDuckGo (DDGS text search) | Real competitor names, market size data, funding round info — grounds claims in searchable fact |
| **news_search** | ChaosAgent | NewsAPI.org | Breaking industry news — justifies radical pivots with real recent events |
| **financial_data** | CFO | exchangerate-api.com | Live USD/LKR, USD/INR, USD/SGD, USD/GBP, USD/EUR rates — anchors burn rate calculations in reality |
| **regulations_search** | Legal | DuckDuckGo (site:gov/legal) | Real regulations and compliance requirements — replaces vague legal warnings with specific citations |

Each tool call flows through the `ToolCallingService`, which emits `tool_call` and `tool_result` WebSocket events visible in the frontend ActivityFeed. Tools have a 10-second timeout and never crash the debate — errors return graceful fallback strings.

---

## How a Debate Works

1. **User submits** a startup problem (e.g., "A food delivery platform for rural Sri Lanka connecting home cooks with local customers")

2. **`primer_running`** — System emits status event, frontend shows "Agents reviewing the problem..."

3. **Memory recall** — ChromaDB queries past debates for relevant context; `memory_recall` event emitted

4. **Persona Factory** — Single LLM call generates 3 dynamic agents with identities tailored to the problem; `persona_generated` events emitted

5. **Primer** — Single LLM call fills all 11 executive agents' dynamic context placeholders; `primer_complete` emitted

6. **Context injection** — Every agent receives its personalised dynamic context + memory context

7. **Debate loop (2 rounds)**:
   - **RoutingAgent** computes turn order based on trust scores; `routing_update` emitted
   - Each agent speaks in sequence:
     - `agent_token` events stream each token live to frontend
     - `agent_message` event delivers completed message with flags and trust deltas
     - **TrustAnalyst** applies trust deltas; `trust_update` emitted with matrix snapshot
     - **ToolCallingService** checks for `tool_call:*` flags, executes tools, injects results, gets grounded response
     - **ReflectionAgent** records the turn, checks objections
   - End of round: **ReflectionAgent** evaluates org health — can trigger `leadership_review`, `debate_stall`, `force_chaos`, `voice_imbalance`, `confidence_crisis`

8. **Summarise** — CEO agent synthesises debate transcript into a 6-part roadmap; `summary` emitted

9. **Store memory** — Compressed summary + tags stored in ChromaDB; `memory_stored` emitted

10. **`debate_complete`** — Final trust matrix snapshot and all flags fired sent to frontend

---

## Tech Stack

| Technology | Category | Why Chosen |
|---|---|---|
| **Python 3.14** | Runtime | Async-native, type-annotated, fast iteration for AI/LLM workflows |
| **FastAPI** | API Framework | Native async/await, native WebSocket support, automatic OpenAPI docs |
| **Uvicorn** | ASGI Server | High-performance async server with hot reload for development |
| **Qwen 3.7-Max** | LLM Backend | 128K context window, JSON mode, streaming support, competitive pricing via Alibaba Cloud |
| **OpenAI SDK** | LLM Client | Compatible with Qwen's DashScope API endpoint; streaming + JSON response format |
| **Pydantic v2** | Data Validation | AgentMessage schema enforcement, trust matrix type safety |
| **ChromaDB** | Vector Database | Persistent semantic memory for debate recall; no external DB server needed |
| **httpx** | HTTP Client | Async HTTP for MCP tool calls (NewsAPI, exchangerate-api.com) |
| **ddgs** | Web Search | DuckDuckGo text search scraper for competitor and regulation research |
| **React 18** | Frontend Framework | Component-based UI with hooks for WebSocket state management |
| **Vite 5** | Build Tool | Fast HMR, ESBuild-based, zero-config React support |
| **TailwindCSS 3** | Styling | Utility-first CSS with custom pixel-font design system |
| **Phaser 3** | Game Engine | Isometric boardroom scene with animated agent avatars |
| **WebSocket** | Real-time Transport | Bidirectional streaming — token-by-token agent speech + system events |

---

## Setup & Run

### Prerequisites

- Python 3.12+
- Node.js 18+
- A Qwen API key from [Aliyun DashScope](https://dashscope.aliyun.com)
- (Optional) A NewsAPI key from [newsapi.org](https://newsapi.org) for real-time news search

### Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install httpx ddgs  # additional tool dependencies

# Configure environment
cp .env.example .env
# Edit .env — add your QWEN_API_KEY and optionally NEWS_API_KEY

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

The frontend runs on `http://localhost:5173` and proxies API requests to the backend at `http://localhost:8000`.

### Quick Test

```bash
# Test all 4 MCP tools from the command line
cd backend
python -c "
import asyncio
from core.tool_service import ToolCallingService

async def test():
    svc = ToolCallingService()
    
    r1 = await svc.execute('web_search', 'food delivery apps Sri Lanka competitors', 'Market Analyst', 'test')
    print('web_search:', r1[:200])
    
    r2 = await svc.execute('news_search', 'food delivery startup disruption', 'Chaos Agent', 'test')
    print('news_search:', r2[:200])
    
    r3 = await svc.execute('financial_data', 'exchange rates', 'CFO', 'test')
    print('financial_data:', r3[:200])
    
    r4 = await svc.execute('regulations_search', 'GDPR data protection', 'Legal', 'test')
    print('regulations_search:', r4[:200])

asyncio.run(test())
"
```

---

## Demo Scenario

### Input
> "A food delivery platform for rural Sri Lanka connecting home cooks with local customers — no restaurants, just home kitchens. Target: villages with 500-5000 population."

### What Happens

The **CEO** opens with a bold vision: "This isn't food delivery — this is economic infrastructure for rural women." The **Market Analyst** fires a `web_search` tool call and returns with real competitor data — PickMe, UberEats, foodpanda already operate in Sri Lanka, but none serve villages under 5000 people. The **CFO** fetches live exchange rates (USD/LKR = 326.27) and calculates a burn rate of $12K/month at 50-village scale — triggers `runway_warning` if they expand beyond 30 villages before monetisation.

The **Chaos Agent** waits until near-consensus forms around a marketplace model, then calls `news_search` and drops a disruption: "Breaking — Swiggy just launched a home-chef pilot in India. They'll be in Sri Lanka within 18 months." The **Legal** agent searches for Sri Lankan food safety regulations — identifies that home-kitchen food sales require health permits under the Food Act No. 26 of 1980, flagging `legal_risk`.

The **Customer Personas** react viscerally — Persona 1 (a home cook named Sandamali) is excited but worried about delivery logistics on unpaved roads. Persona 2 (a sceptical customer) won't trust food safety without visible health ratings. The **Industry Partner** (a regional telecom provider) asks for a 15% revenue share to provide the delivery-rider network.

The **Critic** demolishes the CEO's "we'll scale to 500 villages in year one" claim — the logistics math doesn't work without $2M in delivery fleet investment. The **ReflectionAgent** detects a `debate_stall` on the delivery logistics question and forces a resolution vote.

Final roadmap: Community delivery model (neighbours delivering to neighbours) with an escrow payment system, health-rating badges for every home kitchen, 30-village pilot, 18-month runway target, and a strategic contingency for Swiggy expansion.

---

## Project Structure

```
i-startup-boardroom/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── agents/
│   │   ├── base_agent.py          # BaseAgent + AgentMessage schema
│   │   ├── ceo.py                 # CEO agent
│   │   ├── cto.py                 # CTO agent
│   │   ├── cfo.py                 # CFO agent (tool: financial_data)
│   │   ├── cmo.py                 # CMO agent
│   │   ├── coo.py                 # COO agent
│   │   ├── investor.py            # Investor agent (tool: web_search)
│   │   ├── legal.py               # Legal agent (tool: regulations_search)
│   │   ├── ux.py                  # UX Lead agent
│   │   ├── market_analyst.py      # Market Analyst agent (tool: web_search)
│   │   ├── critic.py              # Critic agent
│   │   ├── chaos.py               # Chaos Agent (tool: news_search)
│   │   ├── customer_persona_1.py  # Dynamic primary user
│   │   ├── customer_persona_2.py  # Dynamic sceptical user
│   │   ├── industry_partner.py    # Dynamic B2B partner
│   │   ├── memory_keeper.py       # Silent system archivist
│   │   └── persona_factory.py     # Generates 3 dynamic agents per debate
│   ├── core/
│   │   ├── orchestrator.py        # 7-step debate pipeline
│   │   ├── tool_service.py        # MCP tool calling hub (4 tools)
│   │   ├── memory_keeper.py       # ChromaDB recall & storage service
│   │   ├── trust_analyst.py       # Trust matrix scoring service
│   │   ├── reflection_agent.py    # Org health monitoring service
│   │   ├── routing_agent.py       # Dynamic turn ordering service
│   │   └── primer.py              # Per-agent context generation
│   └── .env.example               # Environment variable template
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── ActivityFeed.jsx   # Live event stream with tool call cards
│       │   ├── AgentGrid.jsx      # Agent avatar grid
│       │   ├── TrustGraph.jsx     # Trust network visualisation
│       │   ├── PromptInput.jsx    # Problem submission form
│       │   └── StatusBar.jsx      # Debate phase + elapsed time
│       ├── hooks/
│       │   └── useDebateSocket.js # WebSocket connection + event dispatcher
│       └── game/
│           └── BoardroomScene.js  # Isometric Phaser boardroom
├── docs/
│   ├── architecture.md            # System diagram + event catalog
│   └── agent_prompts.md           # All 15 agent prompt documentation
└── README.md                      # This file
```

---

## License

MIT
