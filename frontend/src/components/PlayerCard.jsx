import { formatCoins } from "../lib/api";

export default function PlayerCard({ slot, player, emptyLabel = "No card" }) {
  if (!player) {
    return (
      <article className="player-card empty">
        <div className="slot-badge">{slot}</div>
        <div className="empty-body">
          <span className="empty-icon">∅</span>
          <p>{emptyLabel}</p>
        </div>
      </article>
    );
  }

  return (
    <article className="player-card">
      <div className="slot-badge">{slot}</div>
      <div className="ovr-badge" title={`Overall ${player.overall}`}>
        {player.overall}
      </div>
      <div className="card-media">
        {player.image ? (
          <img src={player.image} alt={player.name} loading="lazy" />
        ) : (
          <div className="img-fallback">{player.position}</div>
        )}
      </div>
      <div className="card-body">
        <h3 className="player-name">{player.name}</h3>
        <p className="player-meta">
          <span className="pos">{player.position}</span>
          <span className="sep">·</span>
          <span className="program">{player.program}</span>
        </p>
        {player.archetype && <p className="archetype">{player.archetype}</p>}
        <div className="stat-row">
          {player.speed != null && (
            <span>
              SPD <strong>{player.speed}</strong>
            </span>
          )}
          {player.awareness != null && (
            <span>
              AWR <strong>{player.awareness}</strong>
            </span>
          )}
          {player.price != null && (
            <span>
              🪙 <strong>{formatCoins(player.price)}</strong>
            </span>
          )}
        </div>
        {player.url && (
          <a
            className="mut-link"
            href={player.url}
            target="_blank"
            rel="noreferrer"
          >
            View on mut.gg ↗
          </a>
        )}
      </div>
    </article>
  );
}
