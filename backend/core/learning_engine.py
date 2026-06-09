"""
Learning Engine — makes agents adapt across debates.
After every debate, analyses outcomes for each agent and updates
their persistent learned_stance stored in SQLite.
This stance is injected into agent prompts as a 4th layer:
  Layer 1: Personality core (fixed)
  Layer 2: Dynamic context (per debate, from primer)
  Layer 3: Behaviour rules (fixed)
  Layer 4: Learned stance (evolves across debates) ← NEW
"""
import sqlite3
import json
import re
from datetime import datetime

DB_PATH = "./trust_history.db"


class LearningEngine:
    def __init__(self, ws_broadcaster=None):
        self.broadcast = ws_broadcaster
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_learned_stances (
                    agent_name   TEXT PRIMARY KEY,
                    stance       TEXT NOT NULL,
                    debate_count INTEGER DEFAULT 0,
                    last_updated TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_debate_outcomes (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    debate_id       TEXT NOT NULL,
                    agent_name      TEXT NOT NULL,
                    trust_delta     REAL DEFAULT 0,
                    flags_fired     TEXT DEFAULT '[]',
                    was_validated   INTEGER DEFAULT 0,
                    recorded_at     TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.commit()

    def load_stance(self, agent_name: str) -> str:
        """Load this agent's current learned stance. Empty string if first debate."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                row = conn.execute(
                    "SELECT stance, debate_count FROM agent_learned_stances WHERE agent_name = ?",
                    (agent_name,)
                ).fetchone()
            if row:
                return f"[After {row[1]} past debates, you have learned: {row[0]}]"
            return ""
        except Exception as e:
            print(f"[LEARNING] load_stance error: {e}")
            return ""

    def load_all_stances(self) -> dict[str, str]:
        """Load learned stances for all agents at startup."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                rows = conn.execute(
                    "SELECT agent_name, stance, debate_count FROM agent_learned_stances"
                ).fetchall()
            stances = {}
            for name, stance, count in rows:
                stances[name] = f"[After {count} past debates, you have learned: {stance}]"
            print(f"[LEARNING] Loaded learned stances for {len(stances)} agents")
            return stances
        except Exception as e:
            print(f"[LEARNING] load_all_stances error: {e}")
            return {}

    def record_outcome(self, debate_id: str, agent_name: str,
                       trust_delta: float, flags_fired: list[str]):
        """Record what happened to this agent in a debate."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    INSERT INTO agent_debate_outcomes
                    (debate_id, agent_name, trust_delta, flags_fired)
                    VALUES (?, ?, ?, ?)
                """, (debate_id, agent_name, trust_delta, json.dumps(flags_fired)))
                conn.commit()
        except Exception as e:
            print(f"[LEARNING] record_outcome error: {e}")

    async def update_stances(self, debate_id: str, debate_summary: str,
                             agent_outcomes: dict, llm_client):
        """
        Called after every debate completes.
        Generates updated learned stance for each agent using LLM.
        agent_outcomes: {agent_name: {trust_delta, flags_fired, messages}}
        """
        if self.broadcast:
            await self.broadcast({
                "type": "learning_started",
                "debate_id": debate_id,
                "message": "Agents processing lessons learned...",
            })

        updated = []
        for agent_name, outcome in agent_outcomes.items():
            try:
                previous_stance = self.load_stance(agent_name)
                trust_delta = outcome.get("trust_delta", 0)
                trust_direction = "gained credibility" if trust_delta > 0 else "lost credibility" if trust_delta < 0 else "neutral"
                flags = outcome.get("flags_fired", [])

                prompt = f"""You are analysing what an AI boardroom agent learned from a completed startup debate.

AGENT: {agent_name}
PAST DEBATE SUMMARY: {debate_summary[:400]}
TRUST CHANGE: {round(trust_delta, 3)} ({trust_direction})
FLAGS FIRED: {', '.join(flags) if flags else 'none'}
PREVIOUS LEARNED STANCE: {previous_stance or 'This is their first debate.'}

Write an updated learned stance for this agent — exactly 3 sentences:
1. What they now believe more strongly based on evidence from this debate
2. What they will do differently in the next debate based on what worked or failed
3. Which type of argument or agent they now treat with more or less trust and why

Be specific to {agent_name}'s role. No generic advice. Return only the 3 sentences."""

                raw = await llm_client.invoke(prompt)
                # Handle potential JSON wrapping if the client forces json_object
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        stance = list(parsed.values())[0].strip()
                    else:
                        stance = raw.strip()
                except json.JSONDecodeError:
                    stance = raw.strip()

                # Save to DB
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("""
                        INSERT INTO agent_learned_stances (agent_name, stance, debate_count, last_updated)
                        VALUES (?, ?, 1, datetime('now'))
                        ON CONFLICT(agent_name) DO UPDATE SET
                            stance = excluded.stance,
                            debate_count = debate_count + 1,
                            last_updated = excluded.last_updated
                    """, (agent_name, stance))
                    conn.commit()

                updated.append(agent_name)
                print(f"[LEARNING] Updated stance for {agent_name}")

            except Exception as e:
                print(f"[LEARNING] Failed to update stance for {agent_name}: {e}")

        if self.broadcast:
            await self.broadcast({
                "type": "learning_complete",
                "debate_id": debate_id,
                "agents_updated": updated,
                "message": f"{len(updated)} agents updated their learned stance",
            })

        return updated
