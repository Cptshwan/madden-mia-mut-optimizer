"""Build an optimized Miami Dolphins MUT roster from available cards."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

# Starting lineup slots for a modern MUT 26 11-on-11 look.
# Multiple slots can share a position pool (e.g. three WRs).
OFFENSE_SLOTS: list[tuple[str, str]] = [
    ("QB", "QB"),
    ("HB", "HB"),
    ("FB", "FB"),
    ("WR1", "WR"),
    ("WR2", "WR"),
    ("WR3", "WR"),
    ("TE", "TE"),
    ("LT", "LT"),
    ("LG", "LG"),
    ("C", "C"),
    ("RG", "RG"),
    ("RT", "RT"),
]

DEFENSE_SLOTS: list[tuple[str, str]] = [
    ("LEDG", "LEDG"),
    ("REDG", "REDG"),
    ("DT1", "DT"),
    ("DT2", "DT"),
    ("SAM", "SAM"),
    ("MIKE", "MIKE"),
    ("WILL", "WILL"),
    ("CB1", "CB"),
    ("CB2", "CB"),
    ("NB", "CB"),  # nickel / slot corner
    ("FS", "FS"),
    ("SS", "SS"),
]

SPECIAL_SLOTS: list[tuple[str, str]] = [
    ("K", "K"),
    ("P", "P"),
    ("LS", "LS"),
]

# Depth chart backups (best remaining after starters)
DEPTH_SLOTS: list[tuple[str, str]] = [
    ("QB2", "QB"),
    ("HB2", "HB"),
    ("WR4", "WR"),
    ("TE2", "TE"),
    ("EDG3", "LEDG"),  # flex edge depth; may also pull REDG
    ("LB4", "MIKE"),
    ("CB4", "CB"),
    ("S3", "FS"),
]

# Fallback pools when a slot's primary position is empty
FALLBACKS: dict[str, list[str]] = {
    "FB": ["HB", "TE"],
    "LS": ["C", "TE"],
    "DT2": ["DT", "LEDG", "REDG"],
    "NB": ["CB", "FS", "SS"],
    "EDG3": ["LEDG", "REDG"],
    "LB4": ["MIKE", "WILL", "SAM"],
    "S3": ["FS", "SS"],
}


def _player_score(
    player: dict[str, Any],
    *,
    prefer_value: bool,
    budget_weight: float,
) -> float:
    """Higher is better. OVR is primary; optional value (OVR per coin)."""
    ovr = float(player.get("overall") or 0)
    price = player.get("price")
    if prefer_value and price and price > 0:
        # Mild efficiency bonus without dominating raw OVR
        efficiency = ovr / (price ** 0.35)
        return ovr * 10 + efficiency * budget_weight
    # Prefer higher max overall / power-up cards slightly
    max_ovr = float(player.get("maxOverall") or ovr)
    bonus = 0.5 if player.get("hasPowerUp") else 0.0
    return ovr * 10 + (max_ovr - ovr) * 0.25 + bonus


def _pool_for(
    position: str, by_position: dict[str, list[dict[str, Any]]], slot_id: str
) -> list[dict[str, Any]]:
    pools = [position] + FALLBACKS.get(slot_id, FALLBACKS.get(position, []))
    seen: set[Any] = set()
    out: list[dict[str, Any]] = []
    for pos in pools:
        for p in by_position.get(pos, []):
            pid = p["id"]
            if pid in seen:
                continue
            seen.add(pid)
            out.append(p)
    return out


def optimize_roster(
    players: list[dict[str, Any]],
    *,
    budget: Optional[int] = None,
    prefer_value: bool = False,
    min_overall: int = 0,
    include_depth: bool = True,
) -> dict[str, Any]:
    """
    Greedy best-OVR (or value) assignment with unique card + unique real-player keys.

    Rules:
    - Each card id used at most once
    - Each real player (playerKey) used at most once so you don't stack clones
    - Optional coin budget across selected cards (cards with unknown price cost 0)
    """
    filtered = [p for p in players if (p.get("overall") or 0) >= min_overall]
    by_position: dict[str, list[dict[str, Any]]] = {}
    for p in filtered:
        by_position.setdefault(p["position"], []).append(p)

    budget_weight = 25.0 if prefer_value else 0.0
    for pos in by_position:
        by_position[pos].sort(
            key=lambda pl: _player_score(pl, prefer_value=prefer_value, budget_weight=budget_weight),
            reverse=True,
        )

    used_card_ids: set[Any] = set()
    used_player_keys: set[str] = set()
    spent = 0

    def pick(slot_id: str, position: str) -> Optional[dict[str, Any]]:
        nonlocal spent
        candidates = _pool_for(position, by_position, slot_id)
        for p in candidates:
            if p["id"] in used_card_ids:
                continue
            if p["playerKey"] in used_player_keys:
                continue
            price = p.get("price") or 0
            if budget is not None and prefer_value is False:
                # Strict budget only when user set a budget without value mode
                if spent + (price or 0) > budget and price:
                    continue
            if budget is not None and prefer_value:
                if price and spent + price > budget:
                    continue
            used_card_ids.add(p["id"])
            used_player_keys.add(p["playerKey"])
            if price:
                spent += int(price)
            return deepcopy(p)
        return None

    def fill(slots: list[tuple[str, str]]) -> list[dict[str, Any]]:
        line: list[dict[str, Any]] = []
        for slot_id, position in slots:
            player = pick(slot_id, position)
            line.append(
                {
                    "slot": slot_id,
                    "position": position,
                    "player": player,
                    "filled": player is not None,
                }
            )
        return line

    offense = fill(OFFENSE_SLOTS)
    defense = fill(DEFENSE_SLOTS)
    special = fill(SPECIAL_SLOTS)
    depth = fill(DEPTH_SLOTS) if include_depth else []

    all_slots = offense + defense + special + depth
    starters = [s for s in offense + defense + special if s["filled"]]
    starter_ovrs = [s["player"]["overall"] for s in starters if s["player"]]
    avg_ovr = round(sum(starter_ovrs) / len(starter_ovrs), 2) if starter_ovrs else 0
    team_ovr = round(sum(starter_ovrs) / max(len(starter_ovrs), 1)) if starter_ovrs else 0

    unfilled = [s["slot"] for s in all_slots if not s["filled"]]

    return {
        "offense": offense,
        "defense": defense,
        "special": special,
        "depth": depth,
        "summary": {
            "starterCount": len(starters),
            "averageOverall": avg_ovr,
            "teamOverall": team_ovr,
            "totalCoins": spent,
            "budget": budget,
            "preferValue": prefer_value,
            "minOverall": min_overall,
            "cardsConsidered": len(filtered),
            "uniquePlayersUsed": len(used_player_keys),
            "unfilledSlots": unfilled,
        },
    }
