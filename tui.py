"""Interactive curses TUI for the Miami Dolphins MUT roster optimizer.

Stays open like a full-screen app until you quit (q / Esc).
Scroll with arrows, Page Up/Down (FN+↑/↓ on KeebDeck), j/k, Home/End.
"""

from __future__ import annotations

import asyncio
import curses
import time
from typing import Any, Callable, Optional


def coins(n: Optional[int]) -> str:
    if n is None or n == 0:
        return "—"
    return f"{n:,}"


def build_lines(
    roster: dict[str, Any],
    pool_size: int,
    elapsed: float,
    status: str,
    include_depth: bool,
) -> list[str]:
    """Build plain text lines for the scrollable viewport."""
    lines: list[str] = []
    summary = roster.get("summary") or {}

    lines.append("MIAMI DOLPHINS  ·  MADDEN 26 MUT  ·  ROSTER OPTIMIZER")
    lines.append("═" * 64)
    lines.append(f"Status: {status}")
    lines.append(
        f"Team OVR {summary.get('teamOverall', '—')}  ·  "
        f"Avg {summary.get('averageOverall', '—')}  ·  "
        f"Pool {pool_size}  ·  "
        f"{elapsed:.1f}s"
    )
    lines.append(
        f"Coins {coins(summary.get('totalCoins'))}  ·  "
        f"Budget {coins(summary.get('budget')) if summary.get('budget') is not None else 'none'}  ·  "
        f"Value {'on' if summary.get('preferValue') else 'off'}"
    )
    unfilled = summary.get("unfilledSlots") or []
    if unfilled:
        lines.append(f"Unfilled: {', '.join(unfilled)}")
    lines.append("")

    def section(title: str, slots: list[dict[str, Any]]) -> None:
        lines.append(f"▸ {title}")
        lines.append("─" * 64)
        lines.append(
            f"  {'SLOT':<6} {'OVR':>3}  {'PLAYER':<24} {'POS':<5} "
            f"{'PROGRAM':<20} {'PRICE':>10}"
        )
        for s in slots or []:
            slot = s.get("slot", "?")
            p = s.get("player")
            if not p:
                lines.append(f"  {slot:<6} {'—':>3}  (unfilled)")
                continue
            name = (p.get("name") or "")[:24]
            prog = (p.get("program") or "")[:20]
            pos = (p.get("position") or s.get("position") or "?")[:5]
            ovr = p.get("overall", 0)
            price = coins(p.get("price"))
            lines.append(
                f"  {slot:<6} {ovr:>3}  {name:<24} {pos:<5} {prog:<20} {price:>10}"
            )
        lines.append("")

    section("OFFENSE", roster.get("offense") or [])
    section("DEFENSE", roster.get("defense") or [])
    section("SPECIAL TEAMS", roster.get("special") or [])
    if include_depth:
        section("DEPTH CHART", roster.get("depth") or [])

    lines.append("─" * 64)
    lines.append(
        "Keys:  ↑↓/jk scroll  ·  PgUp/PgDn (FN+↑↓) page  ·  "
        "g/G top/bottom  ·  r refresh  ·  q quit"
    )
    return lines


class RosterApp:
    def __init__(
        self,
        *,
        fetch_and_optimize: Callable[[], tuple[dict[str, Any], int, float]],
        include_depth: bool,
    ) -> None:
        self.fetch_and_optimize = fetch_and_optimize
        self.include_depth = include_depth
        self.lines: list[str] = ["Loading…"]
        self.offset = 0
        self.status = "Loading…"
        self.error: Optional[str] = None
        self.roster: Optional[dict[str, Any]] = None
        self.pool_size = 0
        self.elapsed = 0.0
        self._need_reload = True

    def reload(self) -> None:
        self.status = "Fetching mut.gg + optimizing…"
        self.error = None
        try:
            roster, pool_size, elapsed = self.fetch_and_optimize()
            self.roster = roster
            self.pool_size = pool_size
            self.elapsed = elapsed
            self.status = "Ready"
            self.lines = build_lines(
                roster, pool_size, elapsed, self.status, self.include_depth
            )
            # Keep scroll in range after refresh
            self.offset = min(self.offset, max(0, len(self.lines) - 1))
        except Exception as exc:  # noqa: BLE001
            self.error = str(exc)
            self.status = "Error"
            self.lines = [
                "MIAMI DOLPHINS  ·  MADDEN 26 MUT",
                "═" * 64,
                f"Failed: {exc}",
                "",
                "Press r to retry  ·  q to quit",
            ]

    def run(self, stdscr: "curses._CursesWindow") -> None:
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        stdscr.keypad(True)
        stdscr.timeout(100)  # wake periodically; allows clean redraws
        if curses.has_colors():
            try:
                curses.start_color()
                curses.use_default_colors()
                curses.init_pair(1, curses.COLOR_CYAN, -1)
                curses.init_pair(2, curses.COLOR_YELLOW, -1)
                curses.init_pair(3, curses.COLOR_GREEN, -1)
                curses.init_pair(4, curses.COLOR_RED, -1)
                curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)
            except curses.error:
                pass

        # First load (blocking inside curses is ok; show status first)
        self._draw(stdscr)
        self.reload()

        while True:
            self._draw(stdscr)
            try:
                ch = stdscr.getch()
            except KeyboardInterrupt:
                break

            if ch == -1:
                continue

            h, _w = stdscr.getmaxyx()
            page = max(1, h - 4)

            if ch in (ord("q"), ord("Q"), 27):  # q or Esc
                break
            if ch in (ord("r"), ord("R")):
                self._draw(stdscr, banner="Refreshing…")
                self.reload()
            elif ch in (curses.KEY_UP, ord("k")):
                self.offset = max(0, self.offset - 1)
            elif ch in (curses.KEY_DOWN, ord("j")):
                self.offset = min(max(0, len(self.lines) - 1), self.offset + 1)
            elif ch in (curses.KEY_PPAGE, curses.KEY_SR):  # Page Up / shift+up
                self.offset = max(0, self.offset - page)
            elif ch in (curses.KEY_NPAGE, curses.KEY_SF):  # Page Down / shift+down
                self.offset = min(max(0, len(self.lines) - page), self.offset + page)
            elif ch in (curses.KEY_HOME, ord("g")):
                self.offset = 0
            elif ch in (curses.KEY_END, ord("G")):
                self.offset = max(0, len(self.lines) - page)
            elif ch == curses.KEY_RESIZE:
                pass

    def _draw(
        self, stdscr: "curses._CursesWindow", banner: Optional[str] = None
    ) -> None:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        if h < 3 or w < 20:
            try:
                stdscr.addstr(0, 0, "Terminal too small")
            except curses.error:
                pass
            stdscr.refresh()
            return

        # Header bar
        title = " MIA MUT 26  "
        help_r = " q:quit r:refresh PgUp/PgDn:scroll "
        header = (title + " " * w)[:w]
        try:
            stdscr.attron(curses.color_pair(5) | curses.A_BOLD)
            stdscr.addstr(0, 0, header)
            if w > len(help_r) + 2:
                stdscr.addstr(0, w - len(help_r) - 1, help_r[: w - 1])
            stdscr.attroff(curses.color_pair(5) | curses.A_BOLD)
        except curses.error:
            pass

        # Body: scrollable lines (rows 1 .. h-2)
        body_h = max(1, h - 2)
        max_off = max(0, len(self.lines) - body_h)
        self.offset = max(0, min(self.offset, max_off))

        for i in range(body_h):
            li = self.offset + i
            if li >= len(self.lines):
                break
            text = self.lines[li]
            if len(text) > w - 1:
                text = text[: w - 1]
            attr = curses.A_NORMAL
            if text.startswith("MIAMI") or text.startswith("═"):
                attr = curses.color_pair(1) | curses.A_BOLD
            elif text.startswith("▸"):
                attr = curses.color_pair(2) | curses.A_BOLD
            elif text.startswith("Failed") or "(unfilled)" in text:
                attr = curses.color_pair(4)
            elif text.startswith("Keys:"):
                attr = curses.A_DIM
            try:
                stdscr.addstr(1 + i, 0, text, attr)
            except curses.error:
                pass

        # Footer / status
        if banner:
            foot = f" {banner} "
        elif self.error:
            foot = f" ERROR: {self.error[: max(0, w - 10)]} "
        else:
            total = len(self.lines)
            shown_end = min(total, self.offset + body_h)
            foot = (
                f" lines {self.offset + 1}-{shown_end}/{total}  ·  "
                f"{self.status}  ·  FN+↑/↓ = Page Up/Down on KeebDeck "
            )
        foot = (foot + " " * w)[:w]
        try:
            stdscr.attron(curses.color_pair(5))
            stdscr.addstr(h - 1, 0, foot)
            stdscr.attroff(curses.color_pair(5))
        except curses.error:
            pass

        stdscr.refresh()


def run_tui(
    *,
    team_id: int,
    budget: Optional[int],
    prefer_value: bool,
    min_overall: int,
    include_depth: bool,
) -> int:
    """Entry point: open full-screen app, return process exit code."""
    # Late import so --help works without backend path issues
    from mut_client import fetch_team_players
    from optimizer import optimize_roster

    def fetch_and_optimize() -> tuple[dict[str, Any], int, float]:
        t0 = time.time()
        players = asyncio.run(fetch_team_players(team_id))
        if not players:
            raise RuntimeError("No Miami Dolphins cards returned from mut.gg")
        roster = optimize_roster(
            players,
            budget=budget,
            prefer_value=prefer_value,
            min_overall=min_overall,
            include_depth=include_depth,
        )
        return roster, len(players), time.time() - t0

    app = RosterApp(
        fetch_and_optimize=fetch_and_optimize,
        include_depth=include_depth,
    )
    try:
        curses.wrapper(app.run)
    except KeyboardInterrupt:
        return 130
    return 0 if not app.error else 1
