"""Reflection Agent — organisational health and restructuring monitor.

Watches debate state and checks health thresholds:
  - CEO trust < 0.40 from 3+ agents   → leadership_review
  - Same objection raised 3x+          → debate_stall
  - One agent > 40% of turns           → voice_imbalance
  - No trust deltas for 5+ turns       → engagement_drop
  - Critic wins 3 consecutive arguments → confidence_crisis

Runs silently after every round. Emits: org_health_event
"""

import json
from dataclasses import dataclass, field
from collections import Counter


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

CEO_TRUST_COLLAPSE_THRESHOLD = 0.40
CEO_TRUST_COLLAPSE_MIN_AGENTS = 3
VOICE_IMBALANCE_THRESHOLD = 0.40   # one agent > 40% of turns
STALL_REPEAT_THRESHOLD = 3         # same objection raised 3+ times
ENGAGEMENT_DROP_TURNS = 5          # no trust deltas for N turns
CRITIC_CONSECUTIVE_WINS = 3        # Critic wins this many in a row


# ---------------------------------------------------------------------------
# Debate state — accumulates across rounds
# ---------------------------------------------------------------------------


@dataclass
class DebateState:
    debate_id: str
    turn_count: int = 0
    agent_turn_counts: dict = field(default_factory=dict)
    raised_objections: list[str] = field(default_factory=list)
    trust_matrix: dict = field(default_factory=dict)
    flags_fired: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Reflection Agent service
# ---------------------------------------------------------------------------


class ReflectionAgent:
    """Organisational health monitor.

    Runs silently after every round. Never participates in debates.
    Emits: org_health_event
    """

    def __init__(self, ws_broadcaster=None):
        self.broadcast = ws_broadcaster  # async callable: broadcast(event_dict)
        self._turns_without_deltas = 0
        self._critic_consecutive_wins = 0

    def set_broadcaster(self, ws_broadcaster) -> None:
        """Set or update the broadcast function (per-debate WebSocket)."""
        self.broadcast = ws_broadcaster

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def evaluate(self, state: DebateState, trust_analyst) -> list[str]:
        """Check all health thresholds after each round.

        Called by orchestrator after every completed round.
        Returns list of event names that were fired.
        """
        events: list[dict] = []

        # 1. CEO trust collapse check
        ceo_trust = trust_analyst.get_trust_toward("CEO")
        low_trust_agents = [
            a for a, score in ceo_trust.items()
            if score < CEO_TRUST_COLLAPSE_THRESHOLD
        ]
        if (
            len(low_trust_agents) >= CEO_TRUST_COLLAPSE_MIN_AGENTS
            and "leadership_review" not in state.flags_fired
        ):
            events.append({
                "event": "leadership_review",
                "reason": (
                    f"{len(low_trust_agents)} agents have trust in CEO below "
                    f"{CEO_TRUST_COLLAPSE_THRESHOLD}"
                ),
                "affected_agents": low_trust_agents,
                "recommended_action": (
                    "Trigger vote — agents elect Acting CEO from CTO, CFO, CMO"
                ),
            })
            state.flags_fired.append("leadership_review")

        # 2. Voice imbalance check
        if state.turn_count > 0:
            for agent, count in state.agent_turn_counts.items():
                ratio = count / state.turn_count
                if (
                    ratio > VOICE_IMBALANCE_THRESHOLD
                    and "voice_imbalance" not in state.flags_fired
                ):
                    events.append({
                        "event": "voice_imbalance",
                        "reason": (
                            f"{agent} has spoken {round(ratio * 100)}% of all turns"
                        ),
                        "affected_agents": [agent],
                        "recommended_action": (
                            f"Mute {agent} for one round, boost lower-turn agents"
                        ),
                    })
                    state.flags_fired.append("voice_imbalance")

        # 3. Debate stall check
        if state.raised_objections:
            objection_counts = Counter(state.raised_objections)
            repeated = [
                (obj, cnt) for obj, cnt in objection_counts.items()
                if cnt >= STALL_REPEAT_THRESHOLD
            ]
            if repeated and "debate_stall" not in state.flags_fired:
                events.append({
                    "event": "debate_stall",
                    "reason": (
                        f"Objection raised {repeated[0][1]} times without "
                        f"resolution: '{repeated[0][0]}'"
                    ),
                    "affected_agents": [],
                    "recommended_action": (
                        "Force resolution vote or escalate to CEO for final decision"
                    ),
                })
                state.flags_fired.append("debate_stall")

        # 4. Engagement drop check
        if (
            self._turns_without_deltas >= ENGAGEMENT_DROP_TURNS
            and "engagement_drop" not in state.flags_fired
        ):
            events.append({
                "event": "engagement_drop",
                "reason": (
                    f"No trust deltas for {self._turns_without_deltas} "
                    f"consecutive turns"
                ),
                "affected_agents": [],
                "recommended_action": (
                    "Introduce Chaos Agent turn or re-prompt stale agents"
                ),
            })
            state.flags_fired.append("engagement_drop")

        # 5. Confidence crisis check (Critic dominance)
        if (
            self._critic_consecutive_wins >= CRITIC_CONSECUTIVE_WINS
            and "confidence_crisis" not in state.flags_fired
        ):
            events.append({
                "event": "confidence_crisis",
                "reason": (
                    f"Critic has won {self._critic_consecutive_wins} "
                    f"consecutive arguments"
                ),
                "affected_agents": ["Critic"],
                "recommended_action": (
                    "Team should reassess core assumptions — Critic may be "
                    "identifying a systemic flaw"
                ),
            })
            state.flags_fired.append("confidence_crisis")

        # Emit all events
        for e in events:
            event = {
                "type": "org_health_event",
                "debate_id": state.debate_id,
                **e,
            }
            if self.broadcast:
                await self.broadcast(event)

        return [e["event"] for e in events]

    # ------------------------------------------------------------------
    # Per-turn tracking (called by orchestrator after each agent speaks)
    # ------------------------------------------------------------------

    def record_turn(
        self, agent: str, state: DebateState, had_trust_deltas: bool
    ) -> None:
        """Call after every agent turn to update counters."""
        state.turn_count += 1
        state.agent_turn_counts[agent] = (
            state.agent_turn_counts.get(agent, 0) + 1
        )
        if had_trust_deltas:
            self._turns_without_deltas = 0
        else:
            self._turns_without_deltas += 1

    def record_objection(self, objection_key: str, state: DebateState) -> None:
        """Call when an agent raises a flagged concern.

        objection_key should be a short normalised string
        e.g. 'runway_warning', 'scalability_concern', 'legal_risk'.
        """
        state.raised_objections.append(objection_key)

    def record_critic_win(self) -> None:
        """Call when the Critic successfully demolishes an argument."""
        self._critic_consecutive_wins += 1

    def reset_critic_streak(self) -> None:
        """Call when someone successfully defends against the Critic."""
        self._critic_consecutive_wins = 0
