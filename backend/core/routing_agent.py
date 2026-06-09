"""Routing Agent — dynamic communication topology controller.

Sets turn order at the start of each debate round based on trust scores.
Recalculates every round so ordering shifts as trust evolves.

Rules:
  - Turn 1 always: CEO (sets the frame)
  - Turn 2 always: the agent with highest trust from CEO
  - Simulated Users: always in turns 8-10, never earlier
  - Chaos Agent: always second-to-last in the round
  - Critic: always last in the round (stress tests the final position)
  - If leadership_review triggered: route to a vote sequence immediately

Emits: routing_update
"""

import json

# ---------------------------------------------------------------------------
# Fixed positions
# ---------------------------------------------------------------------------

FIXED_FIRST = "CEO"
FIXED_LAST = "Critic"
FIXED_SECOND_LAST = "Chaos"

# Agents identified by name (persona names are hardcoded in their agent classes)
SIMULATED_NAMES = {"Customer Persona 1", "Customer Persona 2", "Industry Partner"}

# Role lookup for known agent names (fallback when only names are available)
_NAME_TO_ROLE: dict[str, str] = {
    "CEO": "CEO",
    "CTO": "CTO",
    "CFO": "CFO",
    "CMO": "CMO",
    "COO": "COO",
    "Investor": "Investor",
    "Legal": "Legal Counsel",
    "UX": "UX Lead",
    "MarketAnalyst": "Market Analyst",
    "Critic": "Critic",
    "Chaos": "Chaos Agent",
    "Customer Persona 1": "Customer Persona",
    "Customer Persona 2": "Customer Persona",
    "Industry Partner": "Industry Partner",
}

def _get_role(name: str) -> str:
    """Return the role for a given agent name."""
    return _NAME_TO_ROLE.get(name, "")

# Agents that should never appear in the debate turn order
SYSTEM_AGENTS = {
    "MemoryKeeper", "TrustAnalyst", "ReflectionAgent",
    "RoutingAgent", "Memory Keeper", "Trust Analyst",
    "Reflection Agent", "Routing Agent",
}


# ---------------------------------------------------------------------------
# Routing Agent service
# ---------------------------------------------------------------------------


class RoutingAgent:
    """Dynamic turn-order controller.

    Recalculates order every round based on current trust scores.
    Emits: routing_update
    """

    def __init__(self, ws_broadcaster=None):
        self.broadcast = ws_broadcaster  # async callable: broadcast(event_dict)

    def set_broadcaster(self, ws_broadcaster) -> None:
        """Set or update the broadcast function (per-debate WebSocket)."""
        self.broadcast = ws_broadcaster

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_turn_order(
        self,
        agents: list,              # list of (name, role) tuples or AgentInfo dicts
        trust_analyst,
        round_num: int,
        debate_id: str,
        leadership_review: bool = False,
    ) -> list[str]:
        """Returns ordered list of agent names for this round.

        Args:
            agents: List of (name, role) tuples, or objects with .name/.role.
            trust_analyst: TrustAnalyst instance.
            round_num: Current round number (1-indexed).
            debate_id: Debate identifier.
            leadership_review: If True, route to vote sequence.

        Returns:
            Ordered list of agent name strings.
        """
        if leadership_review:
            return await self._vote_sequence(agents, debate_id)

        # Normalise to (name, role) tuples
        entries = _normalise(agents)

        # Filter to debate-eligible agents only
        eligible = [
            (name, role) for name, role in entries
            if name not in SYSTEM_AGENTS
            and role not in SYSTEM_AGENTS  # belt-and-suspenders
        ]

        # Separate by category
        ceo_entry = None
        chaos_entry = None
        critic_entry = None
        executives: list[tuple[str, str]] = []
        simulated: list[tuple[str, str]] = []

        for name, role in eligible:
            if name == FIXED_FIRST:
                ceo_entry = (name, role)
            elif name == FIXED_SECOND_LAST:
                chaos_entry = (name, role)
            elif name == FIXED_LAST:
                critic_entry = (name, role)
            elif name in SIMULATED_NAMES:
                simulated.append((name, role))
            else:
                executives.append((name, role))

        # Sort executives by CEO's trust toward them (descending)
        executives.sort(
            key=lambda e: trust_analyst.get_trust_from("CEO", e[0]),
            reverse=True,
        )

        # Assemble order
        order: list[str] = []

        # 1. CEO first
        if ceo_entry:
            order.append(ceo_entry[0])

        # 2. Remaining executives in trust order
        order.extend(name for name, _ in executives)

        # 3. Simulated users after executives
        order.extend(name for name, _ in simulated)

        # 4. Chaos Agent second-to-last
        if chaos_entry:
            order.append(chaos_entry[0])

        # 5. Critic always last
        if critic_entry:
            order.append(critic_entry[0])

        # Emit routing event
        reason = "trust_rebalance" if round_num > 1 else "initial_order"
        event = {
            "type": "routing_update",
            "debate_id": debate_id,
            "round": round_num,
            "turn_order": order,
            "reason": reason,
        }
        if self.broadcast:
            await self.broadcast(event)

        return order

    # ------------------------------------------------------------------
    # Vote sequence (leadership review)
    # ------------------------------------------------------------------

    async def _vote_sequence(
        self, agents: list, debate_id: str
    ) -> list[str]:
        """Special turn order for leadership review vote.

        All executive agents vote (no simulated users, no system agents).
        CEO votes last — they are the subject of the review.
        """
        entries = _normalise(agents)

        voters = [
            name for name, role in entries
            if name not in SYSTEM_AGENTS
            and role not in SYSTEM_AGENTS
            and name not in SIMULATED_NAMES
            and name != "CEO"
        ]

        order = voters + ["CEO"]

        event = {
            "type": "routing_update",
            "debate_id": debate_id,
            "round": -1,
            "turn_order": order,
            "reason": "leadership_review",
        }
        if self.broadcast:
            await self.broadcast(event)

        return order


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise(agents: list) -> list[tuple[str, str]]:
    """Convert agents to (name, role) tuples, handling strings, instances, tuples, and dicts."""
    result: list[tuple[str, str]] = []
    for a in agents:
        if isinstance(a, str):
            role = _get_role(a)
            result.append((a, role))
        elif isinstance(a, tuple):
            result.append(a)
        elif hasattr(a, "name") and hasattr(a, "role"):
            result.append((a.name, a.role))
        elif isinstance(a, dict):
            result.append((a.get("name", ""), a.get("role", "")))
    return result
