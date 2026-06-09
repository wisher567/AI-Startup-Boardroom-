"""
Central tool calling hub for all agents.
Agents signal tool calls via flags: ["tool_call:tool_name:query"]
Orchestrator detects these flags, runs the tool, injects result back into agent context,
then calls agent.respond() a second time with the grounded data.
"""

import asyncio
import os
from urllib.parse import quote

import httpx
from ddgs import DDGS

TIMEOUT = 10.0  # seconds — all tools must respond within this window


class ToolCallingService:
    """Executes MCP-style tools for agents during a debate.

    Each tool returns a plain string under 400 characters.  On any error
    the service returns "Tool unavailable: {error}" — it never raises,
    never crashes the debate.
    """

    def __init__(self, ws_broadcaster=None):
        self._broadcaster = ws_broadcaster

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_broadcaster(self, fn):
        """Attach the per-debate broadcast helper."""
        self._broadcaster = fn

    async def execute(
        self,
        tool_name: str,
        query: str,
        agent_name: str,
        debate_id: str,
    ) -> str:
        """Run a tool and return its result string.

        Emits ``tool_call`` before execution and ``tool_result`` afterwards.
        Never raises — errors are returned as the result string.
        """
        # --- emit tool_call event ----------------------------------------
        await self._emit({
            "type": "tool_call",
            "debate_id": debate_id,
            "agent": agent_name,
            "tool": tool_name,
            "query": query,
        })

        # --- dispatch ----------------------------------------------------
        try:
            result = await self._dispatch(tool_name, query)
        except Exception as exc:
            result = f"Tool unavailable: {exc}"

        # --- emit tool_result event --------------------------------------
        await self._emit({
            "type": "tool_result",
            "debate_id": debate_id,
            "agent": agent_name,
            "tool": tool_name,
            "result_preview": result[:200],
        })

        return result

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, tool_name: str, query: str) -> str:
        if tool_name == "web_search":
            return await self._web_search(query)
        elif tool_name == "news_search":
            return await self._news_search(query)
        elif tool_name == "financial_data":
            return await self._financial_data(query)
        elif tool_name == "regulations_search":
            return await self._regulations_search(query)
        else:
            return f"Unknown tool: {tool_name}"

    # ------------------------------------------------------------------
    # Tool 1 — web_search
    # ------------------------------------------------------------------

    async def _web_search(self, query: str) -> str:
        """DuckDuckGo text search via duckduckgo-search scraper.

        Returns up to 3 bullet-point results with titles and snippets.
        """
        def _search():
            try:
                ddgs = DDGS()
                return list(ddgs.text(query, max_results=3))
            finally:
                pass  # DDGS cleans up on GC

        try:
            loop = asyncio.get_event_loop()
            results = await asyncio.wait_for(
                loop.run_in_executor(None, _search),
                timeout=TIMEOUT,
            )
        except asyncio.TimeoutError:
            return "Search timed out."
        except Exception as exc:
            return f"Search unavailable: {str(exc)[:80]}"

        if not results:
            return "No results found."

        lines: list[str] = []
        for r in results[:3]:
            title = r.get("title", "")
            body = r.get("body", "")[:120]
            lines.append(f"• {title}: {body}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Tool 2 — news_search
    # ------------------------------------------------------------------

    async def _news_search(self, query: str) -> str:
        """NewsAPI.org — top 3 articles.

        Requires NEWS_API_KEY in environment.  Falls back gracefully when
        the key is missing or the free tier is exhausted.
        """
        api_key = os.getenv("NEWS_API_KEY", "")
        if not api_key or api_key == "your_key_here":
            return "News API key not configured. Set NEWS_API_KEY in .env to enable real-time news search."

        url = (
            f"https://newsapi.org/v2/everything"
            f"?q={quote(query)}&sortBy=publishedAt&pageSize=3&apiKey={api_key}"
        )

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url)
            data = resp.json()

        if data.get("status") != "ok":
            msg = data.get("message", "News API error")
            return f"News search unavailable: {msg}"[:400]

        articles = data.get("articles", [])
        if not articles:
            return "No recent news articles found for this query."

        lines: list[str] = []
        for art in articles[:3]:
            title = (art.get("title") or "Untitled").strip()
            source = (art.get("source", {}).get("name") or "Unknown")
            lines.append(f"{title} — {source}")

        result = " | ".join(lines)
        return result[:400] if len(result) <= 400 else result[:397] + "..."

    # ------------------------------------------------------------------
    # Tool 3 — financial_data
    # ------------------------------------------------------------------

    async def _financial_data(self, query: str) -> str:
        """Exchange rate data via exchangerate-api.com (no key needed).

        Fetches USD → LKR, INR, SGD, GBP, EUR.
        """
        url = "https://api.exchangerate-api.com/v4/latest/USD"

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url)
            data = resp.json()

        rates = data.get("rates", {})
        if not rates:
            return "No exchange rate data returned."

        parts: list[str] = []
        for currency in ("LKR", "INR", "SGD", "GBP", "EUR"):
            if currency in rates:
                parts.append(f"USD/{currency}={rates[currency]:.2f}")

        date_str = data.get("date", "today")
        return f"Exchange rates ({date_str}): " + ", ".join(parts)

    # ------------------------------------------------------------------
    # Tool 4 — regulations_search
    # ------------------------------------------------------------------

    async def _regulations_search(self, query: str) -> str:
        """DuckDuckGo search targeting official government / legal sources.

        Appends site-restrictions to the query.
        """
        full_query = f"{query} site:gov OR site:legal"
        url = (
            f"https://api.duckduckgo.com/"
            f"?q={quote(full_query)}&format=json&no_html=1&skip_disambig=1"
        )

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url)
            data = resp.json()

        # Prefer AbstractText
        abstract = (data.get("AbstractText") or "").strip()
        if abstract:
            return abstract[:400] if len(abstract) <= 400 else abstract[:397] + "..."

        # Fall back to first RelatedTopic
        topics = data.get("RelatedTopics", [])
        if topics and isinstance(topics[0], dict):
            text = (topics[0].get("Text") or "").strip()
            if text:
                return text[:400] if len(text) <= 400 else text[:397] + "..."

        # Broad fallback — raw search without site restriction
        broad_url = (
            f"https://api.duckduckgo.com/"
            f"?q={quote(query)}&format=json&no_html=1&skip_disambig=1"
        )
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp2 = await client.get(broad_url)
            data2 = resp2.json()

        abstract2 = (data2.get("AbstractText") or "").strip()
        if abstract2:
            return abstract2[:400] if len(abstract2) <= 400 else abstract2[:397] + "..."

        return "No regulatory information found for this query."

    # ------------------------------------------------------------------
    # Health check — lightweight reachability probe for each tool
    # ------------------------------------------------------------------

    async def healthcheck(self) -> list[dict]:
        """Return [{tool, status, latency_ms}] for all 4 tools.

        Each probe uses a 5-second timeout.  All 4 run in parallel so the
        total call is bounded by the slowest tool.

        Status is one of: "reachable", "unreachable", "unconfigured".
        """
        t0 = asyncio.get_event_loop().time()

        async def _probe(name: str, coro) -> dict:
            start = asyncio.get_event_loop().time()
            try:
                await asyncio.wait_for(coro, timeout=5.0)
                latency = round((asyncio.get_event_loop().time() - start) * 1000)
                return {"tool": name, "status": "reachable", "latency_ms": latency}
            except _Unconfigured:
                return {"tool": name, "status": "unconfigured", "latency_ms": None}
            except Exception:
                return {"tool": name, "status": "unreachable", "latency_ms": None}

        class _Unconfigured(Exception):
            pass

        # --- per-tool probe coroutines ----------------------------------

        async def _probe_web_search():
            def _s():
                ddgs = DDGS()
                return list(ddgs.text("test", max_results=1))
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _s)

        async def _probe_news():
            api_key = os.getenv("NEWS_API_KEY", "")
            if not api_key or api_key == "your_key_here":
                raise _Unconfigured("NEWS_API_KEY not set")
            url = f"https://newsapi.org/v2/everything?q=test&pageSize=1&apiKey={api_key}"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                data = resp.json()
                if data.get("status") != "ok":
                    raise RuntimeError(data.get("message", "API error"))

        async def _probe_financial():
            url = "https://api.exchangerate-api.com/v4/latest/USD"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                data = resp.json()
                if not data.get("rates"):
                    raise RuntimeError("No rates returned")

        async def _probe_regulations():
            url = "https://api.duckduckgo.com/?q=test&format=json&no_html=1"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()

        results = await asyncio.gather(
            _probe("web_search",      _probe_web_search()),
            _probe("news_search",      _probe_news()),
            _probe("financial_data",   _probe_financial()),
            _probe("regulations_search", _probe_regulations()),
        )

        total_ms = round((asyncio.get_event_loop().time() - t0) * 1000)
        # Attach total timing as a meta field on the first result only
        if results:
            results[0]["healthcheck_total_ms"] = total_ms
        return results

    # ------------------------------------------------------------------
    # WebSocket helpers
    # ------------------------------------------------------------------

    async def _emit(self, event: dict) -> None:
        """Broadcast a tool event if a broadcaster is attached."""
        if self._broadcaster is None:
            return
        try:
            await self._broadcaster(event)
        except Exception:
            pass  # silent — never crash a debate because of a WS hiccup
