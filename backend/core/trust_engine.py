"""Trust Engine — standalone module for inter-agent trust scoring.

Trust is a dict-of-dicts: trust['CEO']['CTO'] = 0.82
Scores clamped between 0.05 (silenced) and 0.98 (heavy influence).
Persisted to SQLite so scores survive restarts.
"""

import sqlite3
import json
from typing import Optional

# Minimum trust avoids silencing an agent entirely.
# Maximum trust prevents any agent from becoming unquestionable.
MIN_TRUST = 0.05
MAX_TRUST = 0.98
DEFAULT_TRUST = 0.5

# Seed matrix — gives the organization a realistic starting shape.
DEFAULTS: dict[str, dict[str, float]] = {
    "CEO": {
        "CTO": 0.70,
        "CFO": 0.50,
        "CMO": 0.70,
        "COO": 0.65,
        "Investor": 0.40,
        "Legal": 0.55,
        "UX": 0.60,
        "MarketAnalyst": 0.50,
    },
    "CTO": {
        "CEO": 0.65,
        "CFO": 0.60,
        "CMO": 0.45,
        "COO": 0.55,
        "Investor": 0.35,
        "Legal": 0.50,
        "UX": 0.70,
        "MarketAnalyst": 0.45,
    },
    "CFO": {
        "CEO": 0.40,
        "CTO": 0.70,
        "CMO": 0.35,
        "COO": 0.60,
        "Investor": 0.75,
        "Legal": 0.65,
        "UX": 0.30,
        "MarketAnalyst": 0.55,
    },
    "CMO": {
        "CEO": 0.60,
        "CTO": 0.40,
        "CFO": 0.35,
        "COO": 0.55,
        "Investor": 0.30,
        "Legal": 0.45,
        "UX": 0.80,
        "MarketAnalyst": 0.60,
    },
    "COO": {
        "CEO": 0.60,
        "CTO": 0.55,
        "CFO": 0.55,
        "CMO": 0.50,
        "Investor": 0.45,
        "Legal": 0.55,
        "UX": 0.50,
        "MarketAnalyst": 0.40,
    },
    "Investor": {
        "CEO": 0.35,
        "CTO": 0.45,
        "CFO": 0.70,
        "CMO": 0.30,
        "COO": 0.40,
        "Legal": 0.55,
        "UX": 0.25,
        "MarketAnalyst": 0.60,
    },
    "Legal": {
        "CEO": 0.50,
        "CTO": 0.50,
        "CFO": 0.60,
        "CMO": 0.40,
        "COO": 0.55,
        "Investor": 0.50,
        "UX": 0.45,
        "MarketAnalyst": 0.45,
    },
    "UX": {
        "CEO": 0.55,
        "CTO": 0.65,
        "CFO": 0.30,
        "CMO": 0.75,
        "COO": 0.45,
        "Investor": 0.25,
        "Legal": 0.40,
        "MarketAnalyst": 0.50,
    },
    "MarketAnalyst": {
        "CEO": 0.50,
        "CTO": 0.45,
        "CFO": 0.55,
        "CMO": 0.60,
        "COO": 0.40,
        "Investor": 0.60,
        "Legal": 0.45,
        "UX": 0.50,
    },
}

ALL_AGENTS = list(DEFAULTS.keys())


class TrustEngine:
    """Manages inter-agent trust scores with SQLite persistence."""

    def __init__(self, db_path: str = "trust.db"):
        self.scores: dict[str, dict[str, float]] = {}
        self._db_path = db_path
        self._init_db()
        self._load()

    # ------------------------------------------------------------------
    # SQLite persistence
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trust_scores (
                from_agent TEXT NOT NULL,
                to_agent   TEXT NOT NULL,
                score      REAL NOT NULL DEFAULT 0.5,
                PRIMARY KEY (from_agent, to_agent)
            )
            """
        )
        conn.commit()
        conn.close()

    def _load(self) -> None:
        """Load scores from DB, falling back to DEFAULTS for missing rows."""
        # Start with in-memory defaults
        self.scores = {
            src: dict(dests) for src, dests in DEFAULTS.items()
        }

        conn = sqlite3.connect(self._db_path)
        rows = conn.execute("SELECT from_agent, to_agent, score FROM trust_scores").fetchall()
        conn.close()

        # Overlay persisted values on top of defaults
        for from_agent, to_agent, score in rows:
            self.scores.setdefault(from_agent, {})
            self.scores[from_agent][to_agent] = score

    def _persist(self, from_agent: str, to_agent: str) -> None:
        """Write a single trust pair to SQLite (upsert)."""
        score = self.scores.get(from_agent, {}).get(to_agent)
        if score is None:
            return
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            """
            INSERT INTO trust_scores (from_agent, to_agent, score)
            VALUES (?, ?, ?)
            ON CONFLICT(from_agent, to_agent) DO UPDATE SET score = excluded.score
            """,
            (from_agent, to_agent, score),
        )
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, from_agent: str, to_agent: str, delta: float) -> float:
        """Apply a trust delta and return the new score.

        Args:
            from_agent: The agent whose trust is changing.
            to_agent:   The agent being evaluated.
            delta:      Signed float to add (e.g. +0.05 or -0.10).

        Returns:
            The new clamped trust score.
        """
        if from_agent not in self.scores:
            self.scores[from_agent] = {}

        old = self.scores[from_agent].get(to_agent, DEFAULT_TRUST)
        new = round(max(MIN_TRUST, min(MAX_TRUST, old + delta)), 3)
        self.scores[from_agent][to_agent] = new

        self._persist(from_agent, to_agent)
        return new

    def apply_deltas(self, from_agent: str, deltas: dict[str, float]) -> list[dict]:
        """Process all trust_deltas from a single AgentMessage.

        Returns a list of change records for the frontend.
        """
        changes: list[dict] = []
        for target, delta in deltas.items():
            new_score = self.update(from_agent, target, delta)
            changes.append({
                "from": from_agent,
                "to": target,
                "delta": delta,
                "new_score": new_score,
            })
        return changes

    def get_matrix(self) -> dict[str, dict[str, float]]:
        """Return the full trust matrix as a nested dict."""
        return self.scores

    def get_trust(self, from_agent: str, to_agent: str) -> float:
        """Get a single trust score. Returns DEFAULT_TRUST if unknown."""
        return self.scores.get(from_agent, {}).get(to_agent, DEFAULT_TRUST)

    def get_trusted(self, agent: str, threshold: float = 0.6) -> list[str]:
        """Return agents this agent trusts above *threshold*."""
        return [
            target
            for target, score in self.scores.get(agent, {}).items()
            if score >= threshold
        ]

    def get_trusting(self, agent: str, threshold: float = 0.6) -> list[str]:
        """Return agents who trust *agent* above *threshold*."""
        return [
            src
            for src, dests in self.scores.items()
            if dests.get(agent, DEFAULT_TRUST) >= threshold
        ]


# Module-level singleton — import this everywhere.
trust_engine = TrustEngine()

