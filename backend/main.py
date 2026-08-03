"""Miami Dolphins Madden 26 MUT roster optimizer API."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from mut_client import DOLPHINS_TEAM_ID, fetch_team_players
from optimizer import optimize_roster

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Miami Dolphins MUT 26 Roster Optimizer",
    description=(
        "Pulls current Miami Dolphins cards from mut.gg for Madden 26 Ultimate Team "
        "and builds an optimized starting roster + depth chart."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory cache so the UI can re-optimize without re-hitting mut.gg every time
_CACHE: dict[str, Any] = {"players": None, "fetched_at": 0.0, "team_id": None}
CACHE_TTL_SECONDS = 15 * 60


class OptimizeRequest(BaseModel):
    budget: Optional[int] = Field(default=None, ge=0, description="Optional coin budget")
    prefer_value: bool = Field(default=False, description="Prefer OVR-per-coin efficiency")
    min_overall: int = Field(default=0, ge=0, le=99, description="Ignore cards below this OVR")
    include_depth: bool = Field(default=True, description="Include backup depth chart")
    force_refresh: bool = Field(default=False, description="Bypass player cache")


async def _get_players(team_id: int, force_refresh: bool = False) -> list[dict[str, Any]]:
    now = time.time()
    cache_hit = (
        not force_refresh
        and _CACHE["players"] is not None
        and _CACHE["team_id"] == team_id
        and (now - _CACHE["fetched_at"]) < CACHE_TTL_SECONDS
    )
    if cache_hit:
        return _CACHE["players"]

    try:
        players = await fetch_team_players(team_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("mut.gg fetch failed")
        raise HTTPException(status_code=502, detail=f"Failed to fetch MUT data: {exc}") from exc

    if not players:
        raise HTTPException(
            status_code=404,
            detail="No Miami Dolphins cards found. mut.gg may be temporarily unavailable.",
        )

    _CACHE["players"] = players
    _CACHE["fetched_at"] = now
    _CACHE["team_id"] = team_id
    return players


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "game": "Madden 26", "team": "Miami Dolphins"}


@app.get("/api/players")
async def list_players(
    force_refresh: bool = Query(False),
    min_overall: int = Query(0, ge=0, le=99),
    position: Optional[str] = Query(None),
) -> dict[str, Any]:
    players = await _get_players(DOLPHINS_TEAM_ID, force_refresh=force_refresh)
    filtered = [p for p in players if p["overall"] >= min_overall]
    if position:
        filtered = [p for p in filtered if p["position"] == position.upper()]
    by_pos: dict[str, int] = {}
    for p in filtered:
        by_pos[p["position"]] = by_pos.get(p["position"], 0) + 1
    return {
        "teamId": DOLPHINS_TEAM_ID,
        "team": "Miami Dolphins",
        "game": "26",
        "count": len(filtered),
        "byPosition": by_pos,
        "fetchedAt": _CACHE["fetched_at"],
        "players": filtered,
        "source": "https://www.mut.gg",
    }


@app.post("/api/optimize")
async def optimize(body: OptimizeRequest) -> dict[str, Any]:
    players = await _get_players(DOLPHINS_TEAM_ID, force_refresh=body.force_refresh)
    roster = optimize_roster(
        players,
        budget=body.budget,
        prefer_value=body.prefer_value,
        min_overall=body.min_overall,
        include_depth=body.include_depth,
    )
    return {
        "team": "Miami Dolphins",
        "teamId": DOLPHINS_TEAM_ID,
        "game": "Madden 26 Ultimate Team",
        "source": "https://www.mut.gg",
        "fetchedAt": _CACHE["fetched_at"],
        "poolSize": len(players),
        "roster": roster,
    }


@app.get("/api/optimize")
async def optimize_get(
    budget: Optional[int] = Query(None, ge=0),
    prefer_value: bool = Query(False),
    min_overall: int = Query(0, ge=0, le=99),
    include_depth: bool = Query(True),
    force_refresh: bool = Query(False),
) -> dict[str, Any]:
    return await optimize(
        OptimizeRequest(
            budget=budget,
            prefer_value=prefer_value,
            min_overall=min_overall,
            include_depth=include_depth,
            force_refresh=force_refresh,
        )
    )


# Serve built frontend if present
STATIC_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
