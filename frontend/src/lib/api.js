async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export function fetchPlayers({ forceRefresh = false, minOverall = 0 } = {}) {
  const params = new URLSearchParams();
  if (forceRefresh) params.set("force_refresh", "true");
  if (minOverall) params.set("min_overall", String(minOverall));
  const qs = params.toString();
  return request(`/api/players${qs ? `?${qs}` : ""}`);
}

export function optimizeRoster(payload) {
  return request("/api/optimize", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function formatCoins(n) {
  if (n == null || n === 0) return "—";
  return Number(n).toLocaleString();
}

export function formatDate(ts) {
  if (!ts) return "—";
  const d = typeof ts === "number" ? new Date(ts * 1000) : new Date(ts);
  return d.toLocaleString();
}
