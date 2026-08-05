"""Interactive curses TUI for the Miami Dolphins MUT roster optimizer.

Stays open like a full-screen app until you quit (q / Esc on main screen).
Navigate roster slots, open alternates submenu, return with Esc/b.

Keys (main):
  ↑↓ / j k     move selection
  Enter/Space  open top-3 alternates for that position
  PgUp/PgDn    page selection (FN+↑/↓ on KeebDeck)
  g / G        first / last slot
  r            refresh from mut.gg
  q / Esc      quit to shell

Keys (submenu):
  Esc / b / q  return to main roster
  ↑↓           scroll if needed
"""

from __future__ import annotations

import asyncio
import curses
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional


def coins(n: Optional[int]) -> str:
    if n is None or n == 0:
        return "—"
    return f"{n:,}"


@dataclass
class SlotEntry:
    """One selectable roster line."""

    slot: str
    position: str  # pool position (e.g. WR for WR1)
    section: str
    player: Optional[dict[str, Any]]


def _collect_slots(roster: dict[str, Any], include_depth: bool) -> list[SlotEntry]:
    entries: list[SlotEntry] = []
    sections = [
        ("OFFENSE", roster.get("offense") or []),
        ("DEFENSE", roster.get("defense") or []),
        ("SPECIAL TEAMS", roster.get("special") or []),
    ]
    if include_depth:
        sections.append(("DEPTH CHART", roster.get("depth") or []))
    for section, slots in sections:
        for s in slots:
            entries.append(
                SlotEntry(
                    slot=s.get("slot") or "?",
                    position=s.get("position") or "?",
                    section=section,
                    player=s.get("player"),
                )
            )
    return entries


def top_alternates(
    players: list[dict[str, Any]],
    entry: SlotEntry,
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Best alternate cards for this slot's position pool (exclude current athlete)."""
    from optimizer import FALLBACKS

    pos = entry.position
    pools = [pos] + FALLBACKS.get(entry.slot, FALLBACKS.get(pos, []))

    current = entry.player
    current_key = (current or {}).get("playerKey")
    current_id = (current or {}).get("id")

    candidates: list[dict[str, Any]] = []
    seen_ids: set[Any] = set()
    seen_keys: set[str] = set()
    if current_key:
        seen_keys.add(current_key)
    if current_id is not None:
        seen_ids.add(current_id)

    for pool_pos in pools:
        for p in players:
            if p.get("position") != pool_pos:
                continue
            pid = p.get("id")
            pkey = p.get("playerKey") or ""
            if pid in seen_ids:
                continue
            if pkey and pkey in seen_keys:
                continue
            seen_ids.add(pid)
            if pkey:
                seen_keys.add(pkey)
            candidates.append(p)

    candidates.sort(
        key=lambda p: (-(p.get("overall") or 0), p.get("lastName") or "", p.get("firstName") or "")
    )
    return candidates[:limit]


class RosterApp:
    MODE_MAIN = "main"
    MODE_SUB = "sub"

    def __init__(
        self,
        *,
        fetch_and_optimize: Callable[
            [], tuple[dict[str, Any], list[dict[str, Any]], float]
        ],
        include_depth: bool,
    ) -> None:
        self.fetch_and_optimize = fetch_and_optimize
        self.include_depth = include_depth
        self.mode = self.MODE_MAIN
        self.status = "Loading…"
        self.error: Optional[str] = None
        self.roster: Optional[dict[str, Any]] = None
        self.players: list[dict[str, Any]] = []
        self.pool_size = 0
        self.elapsed = 0.0

        self.slots: list[SlotEntry] = []
        self.sel = 0  # selected slot index on main
        self.main_offset = 0  # scroll for main view
        self.sub_offset = 0
        self.sub_entry: Optional[SlotEntry] = None
        self.sub_alts: list[dict[str, Any]] = []
        self.sub_lines: list[str] = []

    def reload(self) -> None:
        self.status = "Fetching mut.gg + optimizing…"
        self.error = None
        try:
            roster, players, elapsed = self.fetch_and_optimize()
            self.roster = roster
            self.players = players
            self.pool_size = len(players)
            self.elapsed = elapsed
            self.slots = _collect_slots(roster, self.include_depth)
            self.status = "Ready"
            if self.sel >= len(self.slots):
                self.sel = max(0, len(self.slots) - 1)
            # If we were in a submenu, rebuild it for the same slot name if possible
            if self.mode == self.MODE_SUB and self.sub_entry:
                slot_name = self.sub_entry.slot
                match = next((e for e in self.slots if e.slot == slot_name), None)
                if match:
                    self._open_sub(match)
                else:
                    self.mode = self.MODE_MAIN
                    self.sub_entry = None
        except Exception as exc:  # noqa: BLE001
            self.error = str(exc)
            self.status = "Error"
            self.slots = []
            self.mode = self.MODE_MAIN

    def _open_sub(self, entry: SlotEntry) -> None:
        self.sub_entry = entry
        self.sub_alts = top_alternates(self.players, entry, limit=3)
        self.sub_offset = 0
        self.sub_lines = self._build_sub_lines(entry, self.sub_alts)
        self.mode = self.MODE_SUB

    def _close_sub(self) -> None:
        self.mode = self.MODE_MAIN
        self.sub_entry = None
        self.sub_alts = []
        self.sub_lines = []
        self.sub_offset = 0

    def _build_sub_lines(
        self, entry: SlotEntry, alts: list[dict[str, Any]]
    ) -> list[str]:
        lines: list[str] = []
        p = entry.player
        lines.append(f"ALTERNATES  ·  slot {entry.slot}  ·  pool {entry.position}")
        lines.append("═" * 64)
        lines.append(f"Section: {entry.section}")
        lines.append("")
        lines.append("▸ CURRENT STARTER")
        lines.append("─" * 64)
        if p:
            lines.append(
                f"  {p.get('overall', 0):>3} OVR  {(p.get('name') or '')[:28]:<28}  "
                f"{(p.get('program') or '')[:18]:<18}  {coins(p.get('price')):>10}"
            )
            if p.get("archetype"):
                lines.append(f"         {p.get('archetype')}")
        else:
            lines.append("  (unfilled)")
        lines.append("")
        lines.append(f"▸ TOP {len(alts)} ALTERNATES  (by overall, unique players)")
        lines.append("─" * 64)
        lines.append(
            f"  {'#':<3} {'OVR':>3}  {'PLAYER':<26} {'POS':<5} "
            f"{'PROGRAM':<18} {'PRICE':>10}"
        )
        if not alts:
            lines.append("  (no other MIA cards at this position)")
        else:
            for i, alt in enumerate(alts, 1):
                lines.append(
                    f"  {i:<3} {alt.get('overall', 0):>3}  "
                    f"{(alt.get('name') or '')[:26]:<26} "
                    f"{(alt.get('position') or '')[:5]:<5} "
                    f"{(alt.get('program') or '')[:18]:<18} "
                    f"{coins(alt.get('price')):>10}"
                )
                # Extra rating context
                bits = []
                for label, key in (
                    ("SPD", "speed"),
                    ("AWR", "awareness"),
                    ("STR", "strength"),
                ):
                    if alt.get(key) is not None:
                        bits.append(f"{label} {alt[key]}")
                if bits:
                    lines.append(f"       {' · '.join(bits)}")
        lines.append("")
        lines.append("─" * 64)
        lines.append("Esc / b / q  →  return to main roster")
        return lines

    def run(self, stdscr: "curses._CursesWindow") -> None:
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        stdscr.keypad(True)
        stdscr.timeout(100)
        if curses.has_colors():
            try:
                curses.start_color()
                curses.use_default_colors()
                curses.init_pair(1, curses.COLOR_CYAN, -1)
                curses.init_pair(2, curses.COLOR_YELLOW, -1)
                curses.init_pair(3, curses.COLOR_GREEN, -1)
                curses.init_pair(4, curses.COLOR_RED, -1)
                curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)
                curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_CYAN)  # selection
                curses.init_pair(7, curses.COLOR_MAGENTA, -1)
            except curses.error:
                pass

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
            page = max(1, h - 5)

            if self.mode == self.MODE_SUB:
                if ch in (27, ord("b"), ord("B"), ord("q"), ord("Q")):
                    self._close_sub()
                elif ch in (curses.KEY_UP, ord("k")):
                    self.sub_offset = max(0, self.sub_offset - 1)
                elif ch in (curses.KEY_DOWN, ord("j")):
                    self.sub_offset = min(
                        max(0, len(self.sub_lines) - 1), self.sub_offset + 1
                    )
                elif ch in (curses.KEY_PPAGE, curses.KEY_SR):
                    self.sub_offset = max(0, self.sub_offset - page)
                elif ch in (curses.KEY_NPAGE, curses.KEY_SF):
                    self.sub_offset = min(
                        max(0, len(self.sub_lines) - page), self.sub_offset + page
                    )
                elif ch in (curses.KEY_HOME, ord("g")):
                    self.sub_offset = 0
                elif ch in (curses.KEY_END, ord("G")):
                    self.sub_offset = max(0, len(self.sub_lines) - page)
                elif ch in (ord("r"), ord("R")):
                    self._draw(stdscr, banner="Refreshing…")
                    self.reload()
                continue

            # ── main mode ──────────────────────────────────────────────
            if ch in (ord("q"), ord("Q"), 27):
                break
            if ch in (ord("r"), ord("R")):
                self._draw(stdscr, banner="Refreshing…")
                self.reload()
            elif ch in (curses.KEY_UP, ord("k")):
                if self.slots:
                    self.sel = max(0, self.sel - 1)
                    self._ensure_sel_visible(h)
            elif ch in (curses.KEY_DOWN, ord("j")):
                if self.slots:
                    self.sel = min(len(self.slots) - 1, self.sel + 1)
                    self._ensure_sel_visible(h)
            elif ch in (curses.KEY_PPAGE, curses.KEY_SR):
                if self.slots:
                    self.sel = max(0, self.sel - page)
                    self._ensure_sel_visible(h)
            elif ch in (curses.KEY_NPAGE, curses.KEY_SF):
                if self.slots:
                    self.sel = min(len(self.slots) - 1, self.sel + page)
                    self._ensure_sel_visible(h)
            elif ch in (curses.KEY_HOME, ord("g")):
                self.sel = 0
                self.main_offset = 0
            elif ch in (curses.KEY_END, ord("G")):
                if self.slots:
                    self.sel = len(self.slots) - 1
                    self._ensure_sel_visible(h)
            elif ch in (curses.KEY_ENTER, 10, 13, ord(" ")):
                if self.slots:
                    self._open_sub(self.slots[self.sel])
            elif ch == curses.KEY_RESIZE:
                self._ensure_sel_visible(h)

    def _ensure_sel_visible(self, term_h: int) -> None:
        """Keep selected slot row in the scroll window."""
        # Approximate: rebuild line map and scroll so selected line is in view
        lines, slot_line = self._main_view_model()
        if not slot_line:
            return
        body_h = max(1, term_h - 2)
        target = slot_line.get(self.sel, 0)
        if target < self.main_offset:
            self.main_offset = target
        elif target >= self.main_offset + body_h:
            self.main_offset = target - body_h + 1
        max_off = max(0, len(lines) - body_h)
        self.main_offset = max(0, min(self.main_offset, max_off))

    def _main_view_model(self) -> tuple[list[tuple[str, Optional[int]]], dict[int, int]]:
        """
        Returns:
          lines: list of (text, slot_index or None)
          slot_line: map slot_index -> line index
        """
        lines: list[tuple[str, Optional[int]]] = []
        slot_line: dict[int, int] = {}
        summary = (self.roster or {}).get("summary") or {}

        def add(text: str, slot_idx: Optional[int] = None) -> None:
            if slot_idx is not None:
                slot_line[slot_idx] = len(lines)
            lines.append((text, slot_idx))

        if self.error and not self.slots:
            add("MIAMI DOLPHINS  ·  MADDEN 26 MUT")
            add("═" * 64)
            add(f"Failed: {self.error}")
            add("")
            add("Press r to retry  ·  q to quit")
            return lines, slot_line

        add("MIAMI DOLPHINS  ·  MADDEN 26 MUT  ·  ROSTER OPTIMIZER")
        add("═" * 64)
        add(f"Status: {self.status}")
        add(
            f"Team OVR {summary.get('teamOverall', '—')}  ·  "
            f"Avg {summary.get('averageOverall', '—')}  ·  "
            f"Pool {self.pool_size}  ·  "
            f"{self.elapsed:.1f}s"
        )
        add(
            f"Coins {coins(summary.get('totalCoins'))}  ·  "
            f"Budget {coins(summary.get('budget')) if summary.get('budget') is not None else 'none'}  ·  "
            f"Value {'on' if summary.get('preferValue') else 'off'}"
        )
        unfilled = summary.get("unfilledSlots") or []
        if unfilled:
            add(f"Unfilled: {', '.join(unfilled)}")
        add("Select a slot → Enter/Space for top 3 alternates")
        add("")

        current_section = None
        for idx, entry in enumerate(self.slots):
            if entry.section != current_section:
                current_section = entry.section
                add(f"▸ {current_section}")
                add("─" * 64)
                add(
                    f"  {'SLOT':<6} {'OVR':>3}  {'PLAYER':<24} {'POS':<5} "
                    f"{'PROGRAM':<18} {'PRICE':>10}"
                )
            p = entry.player
            if not p:
                text = f"  {entry.slot:<6} {'—':>3}  (unfilled)"
            else:
                text = (
                    f"  {entry.slot:<6} {p.get('overall', 0):>3}  "
                    f"{(p.get('name') or '')[:24]:<24} "
                    f"{(p.get('position') or entry.position)[:5]:<5} "
                    f"{(p.get('program') or '')[:18]:<18} "
                    f"{coins(p.get('price')):>10}"
                )
            add(text, idx)

        add("")
        add("─" * 64)
        add(
            "↑↓ select  ·  Enter open alts  ·  PgUp/PgDn page  ·  "
            "r refresh  ·  q quit"
        )
        return lines, slot_line

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

        if self.mode == self.MODE_SUB:
            self._draw_sub(stdscr, h, w, banner)
        else:
            self._draw_main(stdscr, h, w, banner)
        stdscr.refresh()

    def _draw_header(
        self, stdscr: "curses._CursesWindow", w: int, left: str, right: str
    ) -> None:
        header = (left + " " * w)[:w]
        try:
            stdscr.attron(curses.color_pair(5) | curses.A_BOLD)
            stdscr.addstr(0, 0, header)
            if w > len(right) + 2:
                stdscr.addstr(0, max(0, w - len(right) - 1), right[: w - 1])
            stdscr.attroff(curses.color_pair(5) | curses.A_BOLD)
        except curses.error:
            pass

    def _draw_footer(
        self, stdscr: "curses._CursesWindow", h: int, w: int, foot: str
    ) -> None:
        foot = (foot + " " * w)[:w]
        try:
            stdscr.attron(curses.color_pair(5))
            stdscr.addstr(h - 1, 0, foot)
            stdscr.attroff(curses.color_pair(5))
        except curses.error:
            pass

    def _draw_main(
        self,
        stdscr: "curses._CursesWindow",
        h: int,
        w: int,
        banner: Optional[str],
    ) -> None:
        self._draw_header(
            stdscr,
            w,
            " MIA MUT 26  ",
            " Enter:alts  q:quit  r:refresh ",
        )
        lines, _slot_line = self._main_view_model()
        body_h = max(1, h - 2)
        max_off = max(0, len(lines) - body_h)
        self.main_offset = max(0, min(self.main_offset, max_off))
        # Keep selection visible after draws that don't go through key handler
        if self.slots:
            self._ensure_sel_visible(h)
            lines, _slot_line = self._main_view_model()

        for i in range(body_h):
            li = self.main_offset + i
            if li >= len(lines):
                break
            text, slot_idx = lines[li]
            if len(text) > w - 1:
                text = text[: w - 1]
            selected = slot_idx is not None and slot_idx == self.sel
            attr = curses.A_NORMAL
            if selected:
                attr = curses.color_pair(6) | curses.A_BOLD
                # visual marker
                if text.startswith("  "):
                    text = ">" + text[1:]
            elif text.startswith("MIAMI") or text.startswith("═"):
                attr = curses.color_pair(1) | curses.A_BOLD
            elif text.startswith("▸"):
                attr = curses.color_pair(2) | curses.A_BOLD
            elif "Failed" in text or "(unfilled)" in text:
                attr = curses.color_pair(4)
            elif text.startswith("Select") or text.startswith("↑↓"):
                attr = curses.A_DIM
            try:
                stdscr.addstr(1 + i, 0, text, attr)
            except curses.error:
                pass

        if banner:
            foot = f" {banner} "
        elif self.error:
            foot = f" ERROR: {self.error[: max(0, w - 10)]} "
        else:
            n = len(self.slots)
            cur = self.slots[self.sel].slot if self.slots else "—"
            foot = (
                f" slot {self.sel + 1}/{n} [{cur}]  ·  "
                f"{self.status}  ·  FN+↑/↓ page  ·  Enter alts "
            )
        self._draw_footer(stdscr, h, w, foot)

    def _draw_sub(
        self,
        stdscr: "curses._CursesWindow",
        h: int,
        w: int,
        banner: Optional[str],
    ) -> None:
        slot = self.sub_entry.slot if self.sub_entry else "?"
        self._draw_header(
            stdscr,
            w,
            f" ALTS · {slot}  ",
            " Esc/b: back to roster ",
        )
        body_h = max(1, h - 2)
        max_off = max(0, len(self.sub_lines) - body_h)
        self.sub_offset = max(0, min(self.sub_offset, max_off))

        for i in range(body_h):
            li = self.sub_offset + i
            if li >= len(self.sub_lines):
                break
            text = self.sub_lines[li]
            if len(text) > w - 1:
                text = text[: w - 1]
            attr = curses.A_NORMAL
            if text.startswith("ALTERNATES") or text.startswith("═"):
                attr = curses.color_pair(1) | curses.A_BOLD
            elif text.startswith("▸"):
                attr = curses.color_pair(2) | curses.A_BOLD
            elif text.startswith("Esc"):
                attr = curses.A_DIM
            elif "(no other" in text or "(unfilled)" in text:
                attr = curses.color_pair(4)
            elif text.strip()[:1].isdigit() or (
                len(text) > 4 and text[2:5].strip().isdigit()
            ):
                attr = curses.color_pair(3)
            try:
                stdscr.addstr(1 + i, 0, text, attr)
            except curses.error:
                pass

        if banner:
            foot = f" {banner} "
        else:
            foot = (
                f" top {len(self.sub_alts)} alts for {slot}  ·  "
                f"Esc/b/q return  ·  ↑↓ scroll "
            )
        self._draw_footer(stdscr, h, w, foot)


def run_tui(
    *,
    team_id: int,
    budget: Optional[int],
    prefer_value: bool,
    min_overall: int,
    include_depth: bool,
) -> int:
    """Entry point: open full-screen app, return process exit code."""
    from mut_client import fetch_team_players
    from optimizer import optimize_roster

    def fetch_and_optimize() -> tuple[dict[str, Any], list[dict[str, Any]], float]:
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
        return roster, players, time.time() - t0

    app = RosterApp(
        fetch_and_optimize=fetch_and_optimize,
        include_depth=include_depth,
    )
    try:
        curses.wrapper(app.run)
    except KeyboardInterrupt:
        return 130
    return 0 if not app.error else 1
