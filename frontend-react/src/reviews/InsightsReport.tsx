// The Review Insights Agent's report. Numbers shown next to each product come
// from the computed statistics, not from the model.
import { CalendarHeart, Gift, Megaphone, Sparkles, ThumbsUp, TrendingUp, TriangleAlert, Snowflake } from "lucide-react";
import type { ReactNode } from "react";
import { MonthlyBars, Stars, formatNumber } from "./charts";
import type { Insight, ProductStats, Quote } from "./types";

function Quotes({ ids, quotes, max = 2 }: { ids: number[]; quotes: Record<string, Quote>; max?: number }) {
  const found = ids.map((id) => quotes[String(id)]).filter(Boolean).slice(0, max);
  if (!found.length) return null;
  return (
    <div className="quotes">
      {found.map((q) => (
        <blockquote key={q.id} className={`quote quote--${q.sentiment}`}>
          “{q.text}”
          <footer>
            <Stars value={q.rating} size={11} /> · review #{q.id} · {q.date}
          </footer>
        </blockquote>
      ))}
    </div>
  );
}

function Section({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <section className="panel">
      <h3 className="panel__title">
        {icon} {title}
      </h3>
      {children}
    </section>
  );
}

const growth = (g: number | null) =>
  g == null ? "new this year" : `${g > 0 ? "+" : ""}${g}% vs last year`;

export function InsightsReport({ insight }: { insight: Insight }) {
  const { report, stats } = insight;
  const byName = new Map<string, ProductStats>(stats.products.map((p) => [p.name, p]));
  const facts = (name: string, kind: "rating" | "demand" | "season") => {
    const p = byName.get(name);
    if (!p) return null;
    if (kind === "rating")
      return (
        <span className="fact">
          {p.avg_rating != null && <Stars value={p.avg_rating} size={11} />} {p.avg_rating} · net sentiment{" "}
          {p.net_sentiment != null ? `${p.net_sentiment > 0 ? "+" : ""}${p.net_sentiment}` : "–"}
        </span>
      );
    if (kind === "demand")
      return (
        <span className="fact">
          {formatNumber(p.units_12m)} units · ${formatNumber(Math.round(p.revenue_12m))} in the last 12 months ·{" "}
          {growth(p.growth_pct)}
        </span>
      );
    return <span className="fact">{p.december_share_pct}% of the last 12 months' sales were in December (a typical month is ~8%)</span>;
  };

  const xmas = report.christmas;
  return (
    <div className="report">
      <p className="report__summary">{report.summary}</p>

      <section className="xmas">
        <div className="xmas__head">
          <Snowflake size={18} />
          <div>
            <div className="xmas__eyebrow">What to market this Christmas</div>
            <h3 className="xmas__headline">{xmas.headline}</h3>
          </div>
        </div>
        <div className="xmas__grid">
          {xmas.hero_products.map((h) => (
            <article key={h.product} className="hero">
              <div className="hero__name">
                <Gift size={15} /> {h.product}
              </div>
              {facts(h.product, "season")}
              <p className="hero__message">“{h.message}”</p>
              <p className="small">{h.why}</p>
              {h.ideas.length > 0 && (
                <ul className="ticks">
                  {h.ideas.map((idea) => (
                    <li key={idea}>{idea}</li>
                  ))}
                </ul>
              )}
              <Quotes ids={h.review_ids} quotes={report.quotes} />
            </article>
          ))}
        </div>
        <div className="xmas__extras">
          {xmas.bundles.length > 0 && (
            <div>
              <div className="label">Gift bundles</div>
              <ul className="ticks">
                {xmas.bundles.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            </div>
          )}
          {xmas.timing && (
            <div>
              <div className="label">
                <CalendarHeart size={13} /> Timing
              </div>
              <p className="small">{xmas.timing}</p>
            </div>
          )}
          {xmas.avoid.length > 0 && (
            <div>
              <div className="label">Don't feature</div>
              <ul className="plain">
                {xmas.avoid.map((a) => (
                  <li key={a.product}>
                    <strong>{a.product}</strong>: {a.why}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </section>

      <div className="report__grid">
        <Section icon={<ThumbsUp size={16} />} title="Best reviewed">
          <ul className="plain">
            {report.best_reviewed.map((b) => (
              <li key={b.product}>
                <strong>{b.product}</strong> {facts(b.product, "rating")}
                <p className="small">{b.why}</p>
                <Quotes ids={b.review_ids} quotes={report.quotes} max={1} />
              </li>
            ))}
          </ul>
        </Section>
        <Section icon={<TrendingUp size={16} />} title="Most in demand">
          <ul className="plain">
            {report.in_demand.map((d) => (
              <li key={d.product}>
                <strong>{d.product}</strong> {facts(d.product, "demand")}
                <p className="small">{d.why}</p>
              </li>
            ))}
          </ul>
        </Section>
        <Section icon={<CalendarHeart size={16} />} title="Seasonal products">
          <ul className="plain">
            {report.seasonal.map((s) => {
              const p = byName.get(s.product);
              return (
                <li key={s.product}>
                  <strong>{s.product}</strong> <span className="chip">{s.season}</span>
                  {p && <MonthlyBars months={stats.months} units={p.monthly_units} height={26} />}
                  <p className="small">{s.why}</p>
                </li>
              );
            })}
          </ul>
        </Section>
        <Section icon={<TriangleAlert size={16} />} title="Needs attention">
          {report.needs_attention.length ? (
            <ul className="plain">
              {report.needs_attention.map((n) => (
                <li key={n.product}>
                  <strong>{n.product}</strong> {facts(n.product, "rating")}
                  <p className="small">
                    <strong>Issue:</strong> {n.issue}
                    <br />
                    <strong>Fix:</strong> {n.fix}
                  </p>
                  <Quotes ids={n.review_ids} quotes={report.quotes} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="small muted">Nothing stands out.</p>
          )}
        </Section>
      </div>

      <Section icon={<Megaphone size={16} />} title="Recommendations">
        <ol className="recs">
          {report.recommendations.map((r) => (
            <li key={r.action}>
              <span className={`prio prio--${r.priority}`}>{r.priority}</span>
              <div>
                <strong>{r.action}</strong>
                <p className="small">{r.rationale}</p>
              </div>
            </li>
          ))}
        </ol>
      </Section>
      <p className="small muted">
        <Sparkles size={12} /> Written by {insight.model} from {stats.totals.analysed} analysed reviews. Figures next to
        each product are calculated from the dataset, not by the AI.
      </p>
    </div>
  );
}
