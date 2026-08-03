import PlayerCard from "./PlayerCard";

export default function RosterSection({ title, subtitle, slots }) {
  if (!slots?.length) return null;
  return (
    <section className="roster-section">
      <header className="section-header">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        <span className="count-pill">
          {slots.filter((s) => s.filled).length}/{slots.length}
        </span>
      </header>
      <div className="card-grid">
        {slots.map((s) => (
          <PlayerCard
            key={s.slot}
            slot={s.slot}
            player={s.player}
            emptyLabel={`No ${s.position} available`}
          />
        ))}
      </div>
    </section>
  );
}
