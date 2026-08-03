import { formatCoins, formatDate } from "../lib/api";

export default function SummaryBar({ summary, poolSize, fetchedAt }) {
  if (!summary) return null;
  return (
    <div className="summary-bar">
      <div className="stat">
        <span className="label">Team OVR</span>
        <strong className="value glow">{summary.teamOverall}</strong>
      </div>
      <div className="stat">
        <span className="label">Avg starter</span>
        <strong className="value">{summary.averageOverall}</strong>
      </div>
      <div className="stat">
        <span className="label">Starters</span>
        <strong className="value">{summary.starterCount}</strong>
      </div>
      <div className="stat">
        <span className="label">Coins used</span>
        <strong className="value">{formatCoins(summary.totalCoins)}</strong>
      </div>
      <div className="stat">
        <span className="label">MIA pool</span>
        <strong className="value">{poolSize}</strong>
      </div>
      <div className="stat">
        <span className="label">Data as of</span>
        <strong className="value small">{formatDate(fetchedAt)}</strong>
      </div>
    </div>
  );
}
