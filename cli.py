#!/usr/bin/env python3
"""
Miami Dolphins Madden 26 MUT — CLI roster optimizer

Works offline of the web UI. Fetches live cards from mut.gg and prints an
optimized theme-team lineup to the terminal.

Usage:
  ./cli.py
  ./cli.py --min-overall 90 --no-depth
  ./cli.py --budget 500000 --value
  ./cli.py --json roster.json
  ./cli.py --list
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

# Allow running from repo root without installing a package
ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

try:
    from mut_client import DOLPHINS_TEAM_ID, fetch_team_players
    from optimizer import optimize_roster
except ImportError as exc:  # pragma: no cover
    print("Missing dependency. Install with:", file=sys.stderr)
    print("  pip3 install --user --break-system-packages httpx", file=sys.stderr)
    print(f"  ({exc})", file=sys.stderr)
    sys.exit(1)


# ── terminal colors (auto-disable if not a TTY or NO_COLOR) ──────────────────

def _use_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


class C:
    on = _use_color()

    @staticmethod
    def _wrap(code: str, s: str) -> str:
        return f"\033[{code}m{s}\033[0m" if C.on else s

    @staticmethod
    def bold(s: str) -> str:
        return C._wrap("1", s)

    @staticmethod
    def dim(s: str) -> str:
        return C._wrap("2", s)

    @staticmethod
    def aqua(s: str) -> str:
        return C._wrap("38;5;37", s)

    @staticmethod
    def orange(s: str) -> str:
        return C._wrap("38;5;208", s)

    @staticmethod
    def green(s: str) -> str:
        return C._wrap("32", s)

    @staticmethod
    def red(s: str) -> str:
        return C._wrap("31", s)

    @staticmethod
    def yellow(s: str) -> str:
        return C._wrap("33", s)


def ovr_color(ovr: int) -> str:
    s = f"{ovr:>3}"
    if ovr >= 99:
        return C.orange(C.bold(s))
    if ovr >= 95:
        return C.aqua(C.bold(s))
    if ovr >= 90:
        return C.green(s)
    if ovr >= 80:
        return C.yellow(s)
    return C.dim(s)


def coins(n: Optional[int]) -> str:
    if n is None or n == 0:
        return "—"
    return f"{n:,}"


def print_banner() -> None:
    title = "MIAMI DOLPHINS  ·  MADDEN 26 MUT  ·  ROSTER OPTIMIZER"
    bar = "═" * len(title)
    print()
    print(C.aqua(bar))
    print(C.bold(C.aqua(title)))
    print(C.aqua(bar))
    print(C.dim("Live data from mut.gg  ·  best OVR · unique players only"))
    print()


def print_section(title: str) -> None:
    print()
    print(C.orange(C.bold(f"▸ {title}")))
    print(C.dim("─" * 72))


def print_slot_table(slots: list[dict[str, Any]]) -> None:
    # Pad plain strings first, then color — ANSI codes break f-string widths.
    hdr = (
        f"  {'SLOT':<6} {'OVR':>3}  {'PLAYER':<24} {'POS':<5} "
        f"{'PROGRAM':<22} {'PRICE':>12}"
    )
    print(C.dim(hdr))
    for s in slots:
        slot = s["slot"]
        p = s.get("player")
        if not p:
            print(f"  {slot:<6} {C.red('—'):>3}  {C.red('(unfilled)')}")
            continue
        name = p["name"][:24]
        prog = (p.get("program") or "")[:22]
        pos = (p.get("position") or s.get("position") or "?")[:5]
        price = coins(p.get("price"))
        print(
            f"  {C.bold(f'{slot:<6}')} {ovr_color(p['overall'])}  "
            f"{name:<24} {pos:<5} {prog:<22} {C.dim(f'{price:>12}')}"
        )


def print_summary(summary: dict[str, Any], pool_size: int, elapsed: float) -> None:
    print()
    print(C.aqua(C.bold("▸ SUMMARY")))
    print(C.dim("─" * 72))
    rows = [
        ("Team overall", str(summary.get("teamOverall", "—"))),
        ("Avg starter OVR", str(summary.get("averageOverall", "—"))),
        ("Starters filled", str(summary.get("starterCount", "—"))),
        ("Unique players", str(summary.get("uniquePlayersUsed", "—"))),
        ("Cards in pool", str(pool_size)),
        ("Coins (priced cards)", coins(summary.get("totalCoins"))),
        ("Budget", coins(summary.get("budget")) if summary.get("budget") is not None else "none"),
        ("Value mode", "on" if summary.get("preferValue") else "off"),
        ("Min overall filter", str(summary.get("minOverall", 0))),
        ("Fetch + optimize", f"{elapsed:.1f}s"),
    ]
    for label, val in rows:
        print(f"  {label:<22} {C.bold(val)}")
    unfilled = summary.get("unfilledSlots") or []
    if unfilled:
        print(f"  {C.yellow('Unfilled slots'):<31} {', '.join(unfilled)}")
    print()


def print_player_list(players: list[dict[str, Any]], limit: int) -> None:
    print_section(f"MIA CARDS ({len(players)} total, showing top {min(limit, len(players))})")
    print(
        f"  {C.dim('OVR'):>5}  {C.dim('POS'):<5} {C.dim('PLAYER'):<26} "
        f"{C.dim('PROGRAM'):<24} {C.dim('PRICE')}"
    )
    for p in players[:limit]:
        print(
            f"  {ovr_color(p['overall'])}  {p['position']:<5} {p['name'][:26]:<26} "
            f"{(p.get('program') or '')[:24]:<24} {C.dim(coins(p.get('price')))}"
        )
    if len(players) > limit:
        print(C.dim(f"  … and {len(players) - limit} more"))
    print()


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="mia-mut",
        description="Optimize a Miami Dolphins Madden 26 Ultimate Team roster (CLI).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  %(prog)s
  %(prog)s --min-overall 90
  %(prog)s --budget 750000 --value
  %(prog)s --list --limit 50
  %(prog)s --json ~/mia-roster.json --quiet
  %(prog)s --no-color
        """,
    )
    p.add_argument(
        "--min-overall",
        type=int,
        default=0,
        metavar="N",
        help="Ignore cards below this overall (default: 0)",
    )
    p.add_argument(
        "--budget",
        type=int,
        default=None,
        metavar="COINS",
        help="Optional auction-house coin budget",
    )
    p.add_argument(
        "--value",
        action="store_true",
        help="Prefer OVR-per-coin efficiency when prices exist",
    )
    p.add_argument(
        "--no-depth",
        action="store_true",
        help="Skip depth-chart backups",
    )
    p.add_argument(
        "--list",
        action="store_true",
        help="List top MIA cards instead of (or before) optimizing",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=40,
        metavar="N",
        help="How many cards to show with --list (default: 40)",
    )
    p.add_argument(
        "--json",
        metavar="PATH",
        help="Write full roster JSON to PATH (- for stdout)",
    )
    p.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Less banner noise (still prints roster unless --json - only)",
    )
    p.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors",
    )
    p.add_argument(
        "--team-id",
        type=int,
        default=DOLPHINS_TEAM_ID,
        help=argparse.SUPPRESS,  # advanced; default MIA=13
    )
    return p.parse_args(argv)


async def run(args: argparse.Namespace) -> int:
    if args.no_color:
        C.on = False

    if not args.quiet:
        print_banner()
        print(C.dim("Fetching Miami Dolphins MUT 26 cards from mut.gg…"))

    t0 = time.time()
    try:
        players = await fetch_team_players(args.team_id)
    except Exception as exc:  # noqa: BLE001
        print(C.red(f"Failed to fetch mut.gg data: {exc}"), file=sys.stderr)
        print(
            C.dim("Check network access, or try again in a minute."),
            file=sys.stderr,
        )
        return 2

    if not players:
        print(C.red("No cards returned for Miami Dolphins."), file=sys.stderr)
        return 1

    if args.list:
        ranked = sorted(players, key=lambda x: (-x["overall"], x["lastName"]))
        print_player_list(ranked, args.limit)

    roster = optimize_roster(
        players,
        budget=args.budget,
        prefer_value=args.value,
        min_overall=args.min_overall,
        include_depth=not args.no_depth,
    )
    elapsed = time.time() - t0

    payload = {
        "team": "Miami Dolphins",
        "teamId": args.team_id,
        "game": "Madden 26 Ultimate Team",
        "source": "https://www.mut.gg",
        "poolSize": len(players),
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "options": {
            "min_overall": args.min_overall,
            "budget": args.budget,
            "prefer_value": args.value,
            "include_depth": not args.no_depth,
        },
        "roster": roster,
    }

    # Human-readable output (skip only when writing JSON to stdout alone with --quiet)
    json_stdout_only = args.json == "-" and args.quiet
    if not json_stdout_only:
        print_section("OFFENSE")
        print_slot_table(roster["offense"])
        print_section("DEFENSE")
        print_slot_table(roster["defense"])
        print_section("SPECIAL TEAMS")
        print_slot_table(roster["special"])
        if not args.no_depth and roster.get("depth"):
            print_section("DEPTH CHART")
            print_slot_table(roster["depth"])
        print_summary(roster["summary"], len(players), elapsed)

    if args.json:
        text = json.dumps(payload, indent=2)
        if args.json == "-":
            # If we also printed the table, separate JSON clearly
            if not args.quiet:
                print(C.dim("── JSON ──"))
            print(text)
        else:
            out = Path(args.json).expanduser()
            out.write_text(text, encoding="utf-8")
            if not args.quiet:
                print(C.green(f"Wrote {out} ({out.stat().st_size:,} bytes)"))

    return 0


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    try:
        code = asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\n" + C.dim("Aborted."), file=sys.stderr)
        code = 130
    sys.exit(code)


if __name__ == "__main__":
    main()
