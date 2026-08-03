# Miami Dolphins MUT 26 Roster Optimizer

Build an optimized **Miami Dolphins theme-team roster** for **Madden NFL 26 Ultimate Team** using live player data from [mut.gg](https://www.mut.gg).

![Madden 26 · Miami Dolphins](https://img.shields.io/badge/Madden-26-008E97?style=flat-square)
![Team-MIA](https://img.shields.io/badge/Team-Dolphins-FC4C02?style=flat-square)

## What it does

1. Pulls every current **Miami Dolphins** MUT 26 card from mut.gg (queried by position).
2. Assigns the **best available card** to each roster slot (offense, defense, special teams + depth).
3. Enforces **unique real players** (no double-stacking the same athlete across slots).
4. Optionally respects a **coin budget** and a **value** mode (OVR efficiency).

## Quick start

### Requirements

- Python 3.10+ (CLI)
- Node.js 18+ (web UI only)
- `httpx` for live mut.gg fetches

### Linux CLI (this device)

```bash
cd madden-mia-mut-optimizer

# one-time deps (already present if you used the web backend)
pip3 install --user --break-system-packages -r requirements-cli.txt

# run (interactive full-screen app — stays open until q)
./mia-mut
# or
python3 cli.py
```

Inside the app:

| Key | Action |
|-----|--------|
| `↑` `↓` / `j` `k` | Scroll |
| `PgUp` `PgDn` | Page (KeebDeck: **FN + ↑ / ↓**) |
| `g` / `G` | Top / bottom |
| `r` | Refresh from mut.gg |
| `q` / `Esc` | Quit back to the shell |

Useful flags:

```bash
./mia-mut                          # interactive TUI (default)
./mia-mut --once                   # print roster and exit
./mia-mut --list                   # top MIA cards by OVR
./mia-mut --min-overall 90         # ignore low cards
./mia-mut --budget 500000 --value  # coin budget + value mode
./mia-mut --no-depth               # starters only
./mia-mut --json roster.json       # save full JSON
./mia-mut --no-color               # plain text / pipes
./mia-mut --help
```

Optional: put it on your PATH

```bash
mkdir -p ~/.local/bin
ln -sf "$(pwd)/mia-mut" ~/.local/bin/mia-mut
mia-mut
```

### Web UI

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

If `venv` is unavailable on your system:

```bash
pip3 install --user --break-system-packages -r backend/requirements.txt
python3 -m uvicorn main:app --reload --port 8000 --app-dir backend
```

API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173) — Vite proxies `/api` to the backend.

### One-command (production-style)

```bash
# From repo root
./scripts/run.sh
```

This installs deps, builds the UI, and serves everything from FastAPI on port **8000**.

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/players` | All MIA cards (cached ~15 min) |
| `POST` | `/api/optimize` | Build optimized roster |
| `GET` | `/api/optimize` | Same as POST via query params |

### Optimize body

```json
{
  "budget": null,
  "prefer_value": false,
  "min_overall": 0,
  "include_depth": true,
  "force_refresh": false
}
```

## Roster slots

**Offense:** QB, HB, FB, WR×3, TE, LT, LG, C, RG, RT  

**Defense:** LEDG, REDG, DT×2, SAM, MIKE, WILL, CB×2, Nickel CB, FS, SS  

**Special:** K, P, LS  

**Depth:** QB2, HB2, WR4, TE2, EDG3, LB4, CB4, S3  

## How optimization works

- Primary sort: **overall rating** (with a small power-up / max-OVR nudge).
- Value mode: boosts cards with better **OVR-per-coin** when auction prices exist.
- Same `playerKey` (real athlete) can only occupy **one** slot.
- Missing positions fall back to sensible neighbors (e.g. FB ← HB/TE).

Data source is third-party (mut.gg). Ratings, programs, and auction house prices change often — hit **Refresh mut.gg data** after new promos.

## Disclaimer

Not affiliated with EA Sports, Madden, or the Miami Dolphins.  
Player names, ratings, and images are property of their respective owners; card metadata is loaded from mut.gg for personal roster-planning use.

## License

MIT
