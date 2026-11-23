// Small HTML charts (no chart library). Colors come from intel.css:
// sentiment uses a validated diverging scheme (negative red, neutral gray,
// positive blue); single-series bars use one blue. Values are always shown as
// text, and every mark has a hover tooltip.
import type { SentimentStats } from "./types";

const SENTIMENT = [
  { key: "positive", label: "Positive", color: "var(--viz-pos)" },
  { key: "neutral", label: "Neutral", color: "var(--viz-neu)" },
  { key: "negative", label: "Negative", color: "var(--viz-neg)" },
] as const;

function Legend({ items }: { items: { label: string; color: string; value?: string }[] }) {
  return (
    <div className="legend">
      {items.map((item) => (
        <span key={item.label} className="legend__item">
          <span className="legend__swatch" style={{ background: item.color }} />
          {item.label}
          {item.value && <strong>{item.value}</strong>}
        </span>
      ))}
    </div>
  );
}

/** One whole split into positive / neutral / negative, with counts in the legend. */
export function SentimentSplit({ stats }: { stats: SentimentStats }) {
  return (
    <div className="chart">
      <div className="seg-bar" role="img" aria-label={SENTIMENT.map((s) => `${s.label} ${stats.percentages[s.key]}%`).join(", ")}>
        {SENTIMENT.filter((s) => stats.counts[s.key] > 0).map((s) => (
          <span
            key={s.key}
            className="seg-bar__part"
            tabIndex={0}
            data-tip={`${s.label}: ${stats.counts[s.key]} (${stats.percentages[s.key]}%)`}
            style={{ flexGrow: stats.counts[s.key], flexBasis: 0, background: s.color }}
          />
        ))}
      </div>
      <Legend
        items={SENTIMENT.map((s) => ({
          label: s.label,
          color: s.color,
          value: `${stats.percentages[s.key]}% (${stats.counts[s.key]})`,
        }))}
      />
    </div>
  );
}

/** Topics by mention count, each bar stacked by sentiment. */
export function TopicBars({ topics, limit = 10 }: { topics: SentimentStats["topics"]; limit?: number }) {
  const shown = topics.slice(0, limit);
  if (!shown.length) return <p className="muted small">No recurring topics.</p>;
  const max = Math.max(...shown.map((t) => t.mentions));
  return (
    <div className="chart">
      <Legend items={SENTIMENT.map((s) => ({ label: s.label, color: s.color }))} />
      <div className="hbars">
        {shown.map((t) => (
          <div key={t.topic} className="hbar">
            <span className="hbar__label" title={t.topic}>
              {t.topic}
            </span>
            <span className="hbar__track">
              <span className="hbar__stack" style={{ width: `${(t.mentions / max) * 85}%` }}>
                {SENTIMENT.filter((s) => t[s.key] > 0).map((s) => (
                  <span
                    key={s.key}
                    tabIndex={0}
                    data-tip={`${t.topic} · ${s.label}: ${t[s.key]}`}
                    style={{ flexGrow: t[s.key], flexBasis: 0, background: s.color }}
                  />
                ))}
              </span>
              <span className="hbar__value">{t.mentions}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Single-series horizontal bars with the value at the tip (no legend: the title names the series). */
export function BarList({
  rows,
  format = (v) => String(v),
}: {
  rows: { label: string; value: number; tip?: string; display?: string }[];
  format?: (value: number) => string;
}) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="hbars">
      {rows.map((r) => (
        <div key={r.label} className="hbar">
          <span className="hbar__label" title={r.label}>
            {r.label}
          </span>
          <span className="hbar__track">
            <span
              className="hbar__fill"
              tabIndex={0}
              data-tip={r.tip ?? `${r.label}: ${r.display ?? format(r.value)}`}
              style={{ width: `${(r.value / max) * 85}%` }}
            />
            <span className="hbar__value">{r.display ?? format(r.value)}</span>
          </span>
        </div>
      ))}
    </div>
  );
}

/** Rating distribution as columns, with the scale's end labels underneath. */
export function RatingColumns({
  distribution,
  minLabel,
  maxLabel,
}: {
  distribution: { value: number; count: number }[];
  minLabel?: string;
  maxLabel?: string;
}) {
  const max = Math.max(1, ...distribution.map((d) => d.count));
  return (
    <div className="chart">
      <div className="cols">
        {distribution.map((d) => (
          <div key={d.value} className="col">
            <span className="col__value">{d.count}</span>
            <span
              className="col__bar"
              tabIndex={0}
              data-tip={`Rating ${d.value}: ${d.count} response${d.count === 1 ? "" : "s"}`}
              style={{ height: `${(d.count / max) * 100}%` }}
            />
          </div>
        ))}
      </div>
      <div className="col-labels">
        {distribution.map((d) => (
          <span key={d.value}>{d.value}</span>
        ))}
      </div>
      {(minLabel || maxLabel) && (
        <div className="scale-ends">
          <span>{minLabel}</span>
          <span>{maxLabel}</span>
        </div>
      )}
    </div>
  );
}
