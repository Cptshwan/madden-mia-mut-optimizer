export default function Controls({
  options,
  onChange,
  onOptimize,
  onRefresh,
  loading,
}) {
  return (
    <form
      className="controls"
      onSubmit={(e) => {
        e.preventDefault();
        onOptimize();
      }}
    >
      <div className="control-grid">
        <label className="field">
          <span>Min overall</span>
          <input
            type="number"
            min={0}
            max={99}
            value={options.min_overall}
            onChange={(e) =>
              onChange({ ...options, min_overall: Number(e.target.value) || 0 })
            }
          />
        </label>

        <label className="field">
          <span>Coin budget (optional)</span>
          <input
            type="number"
            min={0}
            placeholder="No limit"
            value={options.budget ?? ""}
            onChange={(e) => {
              const v = e.target.value;
              onChange({
                ...options,
                budget: v === "" ? null : Number(v),
              });
            }}
          />
        </label>

        <label className="toggle">
          <input
            type="checkbox"
            checked={options.prefer_value}
            onChange={(e) =>
              onChange({ ...options, prefer_value: e.target.checked })
            }
          />
          <span>Prefer value (OVR / coins)</span>
        </label>

        <label className="toggle">
          <input
            type="checkbox"
            checked={options.include_depth}
            onChange={(e) =>
              onChange({ ...options, include_depth: e.target.checked })
            }
          />
          <span>Include depth chart</span>
        </label>
      </div>

      <div className="actions">
        <button type="submit" className="btn primary" disabled={loading}>
          {loading ? "Building roster…" : "Build optimized roster"}
        </button>
        <button
          type="button"
          className="btn ghost"
          disabled={loading}
          onClick={onRefresh}
        >
          Refresh mut.gg data
        </button>
      </div>
    </form>
  );
}
