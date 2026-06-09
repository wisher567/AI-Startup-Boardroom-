"""Trust Analyst — trust scoring and reputation tracking.

Runs silently after every agent turn — never participates in debates.
Monitors every AgentMessage for trust_deltas, updates the trust matrix,
and tracks reliability over time.

Scoring rules:
  - Base score for new agent pairs: 0.55
  - Accuracy bonus: +0.04 per validated prediction
  - Hallucination penalty: -0.08 per disproven assertion
  - Debate win: +0.06 (when Critic concedes)
  - Debate loss: -0.05 (when Critic successfully demolishes argument)
  - Alliance bonus: +0.03 per successful co-vote
  - Leadership failure: -0.12 applied to all scores toward that agent

Emits: trust_update
"""

import json
import sqlite3
from dataclasses import dataclass, field


DB_PATH = "./trust_history.db"


# ---------------------------------------------------------------------------
# Default trust matrix — gives the organisation a realistic starting shape
# ---------------------------------------------------------------------------

DEFAULTS: dict[str, dict[str, float]] = {
    "CEO": {
        "CTO": 0.70, "CFO": 0.55, "CMO": 0.70, "COO": 0.60,
        "Investor": 0.45, "Legal": 0.50, "UX": 0.55,
        "MarketAnalyst": 0.60, "Critic": 0.50, "Chaos": 0.45,
    },
    "CTO": {
        "CEO": 0.65, "CFO": 0.60, "CMO": 0.50, "COO": 0.65,
        "Investor": 0.50, "Legal": 0.55, "UX": 0.60,
        "MarketAnalyst": 0.65, "Critic": 0.55, "Chaos": 0.40,
    },
    "CFO": {
        "CEO": 0.50, "CTO": 0.70, "CMO": 0.45, "COO": 0.70,
        "Investor": 0.65, "Legal": 0.60, "UX": 0.45,
        "MarketAnalyst": 0.65, "Critic": 0.60, "Chaos": 0.35,
    },
    "CMO": {
        "CEO": 0.75, "CTO": 0.50, "CFO": 0.45, "COO": 0.55,
        "Investor": 0.50, "Legal": 0.45, "UX": 0.70,
        "MarketAnalyst": 0.65, "Critic": 0.45, "Chaos": 0.55,
    },
    "COO": {
        "CEO": 0.65, "CTO": 0.65, "CFO": 0.70, "CMO": 0.55,
        "Investor": 0.55, "Legal": 0.60, "UX": 0.55,
        "MarketAnalyst": 0.60, "Critic": 0.55, "Chaos": 0.40,
    },
    "Investor": {
        "CEO": 0.40, "CTO": 0.65, "CFO": 0.70, "CMO": 0.45,
        "COO": 0.55, "Legal": 0.60, "UX": 0.45,
        "MarketAnalyst": 0.75, "Critic": 0.70, "Chaos": 0.35,
    },
    "Legal": {
        "CEO": 0.55, "CTO": 0.60, "CFO": 0.65, "CMO": 0.50,
        "COO": 0.60, "Investor": 0.55, "UX": 0.55,
        "MarketAnalyst": 0.60, "Critic": 0.60, "Chaos": 0.35,
    },
    "UX": {
        "CEO": 0.60, "CTO": 0.55, "CFO": 0.45, "CMO": 0.70,
        "COO": 0.55, "Investor": 0.45, "Legal": 0.50,
        "MarketAnalyst": 0.60, "Critic": 0.50, "Chaos": 0.50,
    },
    "MarketAnalyst": {
        "CEO": 0.60, "CTO": 0.65, "CFO": 0.65, "CMO": 0.60,
        "COO": 0.60, "Investor": 0.70, "Legal": 0.55,
        "UX": 0.55, "Critic": 0.65, "Chaos": 0.40,
    },
    "Critic": {
        "CEO": 0.45, "CTO": 0.65, "CFO": 0.65, "CMO": 0.40,
        "COO": 0.55, "Investor": 0.65, "Legal": 0.60,
        "UX": 0.50, "MarketAnalyst": 0.65, "Chaos": 0.40,
    },
    "Chaos": {
        "CEO": 0.55, "CTO": 0.45, "CFO": 0.35, "CMO": 0.60,
        "COO": 0.40, "Investor": 0.40, "Legal": 0.35,
        "UX": 0.60, "MarketAnalyst": 0.50, "Critic": 0.45,
    },
}

# Score clamps — never 0 (silence) or 1.0 (unquestionable)
MIN_TRUST = 0.05
MAX_TRUST = 0.98
DEFAULT_TRUST = 0.55


# ---------------------------------------------------------------------------
# Penalty mappings
# ---------------------------------------------------------------------------

PENALTIES: dict[str, float] = {
    "leadership_failure": -0.12,
    "hallucination":      -0.08,
    "prediction_failed":  -0.04,
    "debate_loss":        -0.05,
}

BONUSES: dict[str, float] = {
    "prediction_validated": +0.04,
    "debate_win":           +0.06,
    "alliance":             +0.03,
}


# ---------------------------------------------------------------------------
# Trust Analyst service
# ---------------------------------------------------------------------------


class TrustAnalyst:
    """Trust scoring service.

    Runs silently after every agent turn. Never participates in debates.
    Emits: trust_update
    """

    # ------------------------------------------------------------------
    # SQLite persistence
    # ------------------------------------------------------------------

    def _init_db(self):
        """Create trust table if it doesn't exist."""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trust_matrix (
                    from_agent TEXT NOT NULL,
                    to_agent   TEXT NOT NULL,
                    score      REAL NOT NULL,
                    updated_at TEXT DEFAULT (datetime('now')),
                    PRIMARY KEY (from_agent, to_agent)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trust_history (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    debate_id  TEXT NOT NULL,
                    from_agent TEXT NOT NULL,
                    to_agent   TEXT NOT NULL,
                    old_score  REAL NOT NULL,
                    new_score  REAL NOT NULL,
                    delta      REAL NOT NULL,
                    recorded_at TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.commit()

    def load_from_db(self):
        """
        Load persisted trust scores from SQLite into memory.
        Called once at startup. Overwrites DEFAULTS for any pair that exists in DB.
        """
        try:
            with sqlite3.connect(DB_PATH) as conn:
                rows = conn.execute(
                    "SELECT from_agent, to_agent, score FROM trust_matrix"
                ).fetchall()

            loaded = 0
            for from_agent, to_agent, score in rows:
                if from_agent not in self.scores:
                    self.scores[from_agent] = {}
                self.scores[from_agent][to_agent] = score
                loaded += 1

            print(f"[TRUST] Loaded {loaded} persisted trust scores from SQLite")
        except Exception as e:
            print(f"[TRUST] No existing trust DB found, starting from defaults: {e}")

    def save_to_db(self, debate_id: str, updates: list[dict]):
        """
        Persist current trust scores after every update.
        Also writes to trust_history for full audit trail.
        """
        try:
            with sqlite3.connect(DB_PATH) as conn:
                # Upsert current scores
                for update in updates:
                    conn.execute("""
                        INSERT INTO trust_matrix (from_agent, to_agent, score, updated_at)
                        VALUES (?, ?, ?, datetime('now'))
                        ON CONFLICT(from_agent, to_agent) DO UPDATE SET
                            score = excluded.score,
                            updated_at = excluded.updated_at
                    """, (update["from"], update["to"], update["new"]))

                    # Write history record
                    conn.execute("""
                        INSERT INTO trust_history
                        (debate_id, from_agent, to_agent, old_score, new_score, delta)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (debate_id, update["from"], update["to"],
                          update["old"], update["new"], update["delta"]))

                conn.commit()
        except Exception as e:
            print(f"[TRUST] DB save error: {e}")

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def __init__(self, ws_broadcaster=None):
        self.scores: dict[str, dict[str, float]] = {
            agent: dict(targets) for agent, targets in DEFAULTS.items()
        }
        self.broadcast = ws_broadcaster  # async callable: broadcast(event_dict)
        self._init_db()
        self.load_from_db()  # overwrite defaults with persisted scores

    def set_broadcaster(self, ws_broadcaster) -> None:
        """Set or update the broadcast function (per-debate WebSocket)."""
        self.broadcast = ws_broadcaster

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def _clamp(self, value: float) -> float:
        return round(max(MIN_TRUST, min(MAX_TRUST, value)), 3)

    async def apply_deltas(
        self,
        from_agent: str,
        trust_deltas: dict[str, float],
        debate_id: str,
    ) -> None:
        """Apply trust_deltas emitted by an agent after their turn.

        Called by orchestrator after every AgentMessage.
        """
        if not trust_deltas:
            return

        updates: list[dict] = []
        if from_agent not in self.scores:
            self.scores[from_agent] = {}

        for to_agent, delta in trust_deltas.items():
            old = self.scores[from_agent].get(to_agent, DEFAULT_TRUST)
            new = self._clamp(old + delta)
            self.scores[from_agent][to_agent] = new
            updates.append({
                "from": from_agent,
                "to": to_agent,
                "old": old,
                "new": new,
                "delta": round(delta, 3),
            })

        # Persist to SQLite
        self.save_to_db(debate_id, updates)

        event = {
            "type": "trust_update",
            "debate_id": debate_id,
            "updates": updates,
            "matrix_snapshot": self.get_snapshot(),
        }
        if self.broadcast:
            await self.broadcast(event)

    async def apply_penalty(
        self, agent: str, reason: str, debate_id: str
    ) -> None:
        """Apply a global trust penalty toward an agent from all others.

        Used on leadership failure, repeated hallucinations, etc.
        """
        delta = PENALTIES.get(reason, -0.05)
        updates: list[dict] = []

        for from_agent, targets in self.scores.items():
            if from_agent == agent:
                continue  # don't penalise self-trust
            if agent in targets:
                old = targets[agent]
                new = self._clamp(old + delta)
                targets[agent] = new
                updates.append({
                    "from": from_agent,
                    "to": agent,
                    "old": old,
                    "new": new,
                    "delta": delta,
                })

        event = {
            "type": "trust_update",
            "debate_id": debate_id,
            "reason": reason,
            "updates": updates,
            "matrix_snapshot": self.get_snapshot(),
        }
        if self.broadcast:
            await self.broadcast(event)

    async def apply_bonus(
        self, from_agent: str, to_agent: str, reason: str, debate_id: str
    ) -> None:
        """Apply a specific trust bonus between two agents.

        Used for debate wins, alliances, validated predictions.
        """
        delta = BONUSES.get(reason, 0.03)
        if from_agent not in self.scores:
            self.scores[from_agent] = {}
        old = self.scores[from_agent].get(to_agent, DEFAULT_TRUST)
        new = self._clamp(old + delta)
        self.scores[from_agent][to_agent] = new

        event = {
            "type": "trust_update",
            "debate_id": debate_id,
            "reason": reason,
            "updates": [{
                "from": from_agent,
                "to": to_agent,
                "old": old,
                "new": new,
                "delta": delta,
            }],
            "matrix_snapshot": self.get_snapshot(),
        }
        if self.broadcast:
            await self.broadcast(event)

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def get_snapshot(self) -> dict[str, dict[str, float]]:
        """Full trust matrix as nested dict."""
        return {a: dict(t) for a, t in self.scores.items()}

    def get_trust_from(self, from_agent: str, to_agent: str) -> float:
        """Single directional trust score."""
        return self.scores.get(from_agent, {}).get(to_agent, DEFAULT_TRUST)

    def get_trust_toward(self, agent: str) -> dict[str, float]:
        """Average trust all agents have toward this agent."""
        result: dict[str, float] = {}
        for from_agent, targets in self.scores.items():
            if agent in targets:
                result[from_agent] = targets[agent]
        return result
