import { useCallback, useState } from "react";
import Controls from "./components/Controls";
import RosterSection from "./components/RosterSection";
import SummaryBar from "./components/SummaryBar";
import { optimizeRoster } from "./lib/api";

const DEFAULT_OPTIONS = {
  budget: null,
  prefer_value: false,
  min_overall: 0,
  include_depth: true,
  force_refresh: false,
};

export default function App() {
  const [options, setOptions] = useState(DEFAULT_OPTIONS);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const runOptimize = useCallback(
    async (overrides = {}) => {
      setLoading(true);
      setError(null);
      try {
        const payload = { ...options, ...overrides };
        const data = await optimizeRoster(payload);
        setResult(data);
      } catch (err) {
        setError(err.message || "Something went wrong");
      } finally {
        setLoading(false);
      }
    },
    [options]
  );

  const roster = result?.roster;

  return (
    <div className="app">
      <div className="bg-orb orb-a" aria-hidden />
      <div className="bg-orb orb-b" aria-hidden />

      <header className="hero">
        <div className="brand">
          <div className="logo-mark" aria-hidden>
            🐬
          </div>
          <div>
            <p className="eyebrow">Madden 26 Ultimate Team</p>
            <h1>Miami Dolphins Roster Optimizer</h1>
            <p className="lede">
              Live cards from{" "}
              <a href="https://www.mut.gg/players/?team_id=13" target="_blank" rel="noreferrer">
                mut.gg
              </a>
              , auto-built into a best-available Fins theme-team lineup. Unique
              players only — highest OVR wins each slot.
            </p>
          </div>
        </div>
      </header>

      <main className="main">
        <Controls
          options={options}
          onChange={setOptions}
          onOptimize={() => runOptimize({ force_refresh: false })}
          onRefresh={() => runOptimize({ force_refresh: true })}
          loading={loading}
        />

        {error && (
          <div className="banner error" role="alert">
            <strong>Could not build roster.</strong> {error}
          </div>
        )}

        {!result && !loading && !error && (
          <div className="banner idle">
            Hit <strong>Build optimized roster</strong> to pull current Dolphins
            MUT cards and generate your lineup.
          </div>
        )}

        {loading && (
          <div className="banner loading">
            <span className="spinner" /> Fetching Dolphins cards & optimizing…
          </div>
        )}

        {result && roster && (
          <>
            <SummaryBar
              summary={roster.summary}
              poolSize={result.poolSize}
              fetchedAt={result.fetchedAt}
            />

            {roster.summary.unfilledSlots?.length > 0 && (
              <div className="banner warn">
                Unfilled slots: {roster.summary.unfilledSlots.join(", ")}. Not
                enough unique Dolphins cards at those positions yet.
              </div>
            )}

            <RosterSection
              title="Offense"
              subtitle="Best available skill positions & O-line"
              slots={roster.offense}
            />
            <RosterSection
              title="Defense"
              subtitle="Edges, front, linebackers & secondary"
              slots={roster.defense}
            />
            <RosterSection
              title="Special teams"
              subtitle="Kicker, punter, long snapper"
              slots={roster.special}
            />
            {options.include_depth && (
              <RosterSection
                title="Depth chart"
                subtitle="Top backups after starters are locked"
                slots={roster.depth}
              />
            )}
          </>
        )}
      </main>

      <footer className="footer">
        <p>
          Not affiliated with EA Sports or the Miami Dolphins. Player ratings &
          images © EA / sourced via{" "}
          <a href="https://www.mut.gg" target="_blank" rel="noreferrer">
            mut.gg
          </a>
          .
        </p>
      </footer>
    </div>
  );
}
