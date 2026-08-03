"""Client for mut.gg Madden 26 Ultimate Team player data."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://www.mut.gg"
GAME = "26"
DOLPHINS_TEAM_ID = 13

# MUT 26 game positions (abbreviations used by mut.gg filters)
POSITIONS = [
    "QB",
    "HB",
    "FB",
    "WR",
    "TE",
    "LT",
    "LG",
    "C",
    "RG",
    "RT",
    "LEDG",
    "REDG",
    "DT",
    "SAM",
    "MIKE",
    "WILL",
    "CB",
    "FS",
    "SS",
    "K",
    "P",
    "LS",
]

HEADERS = {
    "User-Agent": (
        "MiamiDolphinsMUTOptimizer/1.0 (+https://github.com/Cptshwan/madden-mia-mut-optimizer)"
    ),
    "Accept": "application/json",
}


def _simplify_player(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a mut.gg player-item payload for the app."""
    team = raw.get("team") or {}
    program = raw.get("program") or {}
    game_pos = raw.get("gamePosition") or {}
    archetype = raw.get("archetype") or {}
    image = raw.get("image") or {}
    full_image = raw.get("fullImage") or {}
    player = raw.get("player") or {}

    price_fields = {
        "ps5": raw.get("ps5Price"),
        "xbox": raw.get("xbsxPrice"),
        "pc": raw.get("pcPrice"),
    }
    # Prefer the first known market price
    price = next((v for v in price_fields.values() if isinstance(v, (int, float)) and v > 0), None)

    first = (raw.get("firstName") or "").strip()
    last = (raw.get("lastName") or "").strip()
    # Prefer real-world name for uniqueness so Golden Ticket / shapeshifter /
    # position-hero variants of the same athlete cannot occupy multiple slots.
    name_key = f"{first}|{last}".lower()
    mut_player_id = player.get("id") or player.get("externalId")
    player_key = name_key or str(mut_player_id or raw.get("externalId"))

    return {
        "id": raw.get("externalId"),
        "pk": raw.get("pk"),
        "playerKey": player_key,
        "mutPlayerId": mut_player_id,
        "firstName": first,
        "lastName": last,
        "name": f"{first} {last}".strip(),
        "overall": raw.get("overall") or 0,
        "maxOverall": raw.get("maxOverall") or raw.get("overall") or 0,
        "position": game_pos.get("abbreviation") or "?",
        "positionName": game_pos.get("name") or "",
        "archetype": archetype.get("name") or archetype.get("nameWithoutPosition") or "",
        "team": {
            "id": team.get("id"),
            "name": team.get("name"),
            "abbreviation": team.get("abbreviation"),
            "primaryHex": team.get("primaryHexColor") or "#008E97",
            "secondaryHex": team.get("secondaryHexColor") or "#FC4C02",
        },
        "program": program.get("name") or "Unknown",
        "programId": program.get("id"),
        "image": image.get("url"),
        "fullImage": full_image.get("url"),
        "url": f"https://www.mut.gg{raw.get('url')}" if raw.get("url") else None,
        "price": price,
        "prices": price_fields,
        "hasPowerUp": bool(raw.get("hasPowerUp")),
        "isLtd": bool(raw.get("isLtd")),
        "speed": raw.get("speed"),
        "acceleration": raw.get("acceleration"),
        "awareness": raw.get("awareness"),
        "strength": raw.get("strength"),
        "agility": raw.get("agility"),
        "throwPower": raw.get("throwPower"),
        "catching": raw.get("catching"),
        "tackle": raw.get("tackle"),
        "manCoverage": raw.get("manCoverage"),
        "zoneCoverage": raw.get("zoneCoverage"),
        "passBlock": raw.get("passBlock"),
        "runBlock": raw.get("runBlock"),
        "releaseDate": raw.get("releaseDate"),
    }


async def _fetch_position(
    client: httpx.AsyncClient, team_id: int, position: str
) -> list[dict[str, Any]]:
    params = {"team_id": team_id, "positions": position}
    url = f"{BASE_URL}/api/{GAME}/player-items/"
    try:
        resp = await client.get(url, params=params, headers=HEADERS, timeout=30.0)
        resp.raise_for_status()
        payload = resp.json()
        return payload.get("data") or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed fetching %s: %s", position, exc)
        return []


async def fetch_team_players(team_id: int = DOLPHINS_TEAM_ID) -> list[dict[str, Any]]:
    """Fetch all MUT 26 cards for a team by querying each position."""
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[_fetch_position(client, team_id, pos) for pos in POSITIONS]
        )

    by_id: dict[Any, dict[str, Any]] = {}
    for batch in results:
        for raw in batch:
            simplified = _simplify_player(raw)
            pid = simplified["id"]
            if pid is None:
                continue
            existing = by_id.get(pid)
            if existing is None or simplified["overall"] > existing["overall"]:
                by_id[pid] = simplified

    players = sorted(
        by_id.values(),
        key=lambda p: (-p["overall"], p["position"], p["lastName"], p["firstName"]),
    )
    logger.info("Fetched %d unique cards for team_id=%s", len(players), team_id)
    return players


async def fetch_core_teams() -> list[dict[str, Any]]:
    """Optional helper: list teams from mut.gg core data."""
    url = f"{BASE_URL}/api/{GAME}/core-data/"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS, timeout=30.0)
        resp.raise_for_status()
        data = resp.json().get("data") or {}
        return data.get("teams") or []
