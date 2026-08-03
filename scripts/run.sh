#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="${HOME}/.local/bin:${PATH}"

echo "==> Installing backend deps"
if python3 -m venv backend/.venv 2>/dev/null; then
  # shellcheck disable=SC1091
  source backend/.venv/bin/activate
  pip install -q -r backend/requirements.txt
else
  echo "    (venv unavailable — installing with --user --break-system-packages)"
  pip3 install --user --break-system-packages -q -r backend/requirements.txt
fi

echo "==> Installing & building frontend"
cd frontend
npm install
npm run build
cd "$ROOT"

echo "==> Starting server on http://127.0.0.1:8000"
cd backend
exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
