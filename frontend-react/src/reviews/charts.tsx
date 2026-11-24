// Small charts for the reviews page: sentiment split, monthly demand, star ratings.
// Colors: blue/red diverging poles with a gray neutral midpoint (validated for
// color-vision deficiency); demand uses one amber hue, Nov–Dec in its darker step.
import { useState } from "react";
import { Star } from "lucide-react";
import type { Sentiment } from "./types";

export const SENTIMENT_LABEL: Record<Sentiment, string> = {
  positive: "Positive",
  neutral: "Neutral",
  negative: "Negative",
};

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const monthLabel = (iso: string) => `${MONTH_NAMES[Number(iso.slice(5, 7)) - 1]} ${iso.slice(0, 4)}`;
export const formatNumber = (n: number) => n.toLocaleString();

/** Legend shared by every sentiment bar on the page. */
export function SentimentLegend() {
  return (
    <div className="legend" aria-hidden="true">
      {(["positive", "neutral", "negative"] as Sentiment[]).map((s) => (
        <span key={s} className="legend__item">
          <span className={`legend__swatch sent--${s}`} />
          {SENTIMENT_LABEL[s]}
        </span>
      ))}
    </div>
  );
}

/** 100% stacked bar of positive / neutral / negative shares, with a hover readout. */
export function SentimentBar({ pct, counts }: { pct: Record<Sentiment, number | null>; counts: Record<Sentiment, number> }) {
  const [hover, setHover] = useState<Sentiment | null>(null);
  if (pct.positive == null) return <span className="muted small">Not analysed yet</span>;
  const order: Sentiment[] = ["positive", "neutral", "negative"];
  const summary = order.map((s) => `${SENTIMENT_LABEL[s]} ${pct[s]}% (${counts[s]})`).join(", ");
  return (
    <div className="sentbar" role="img" aria-label={summary}>
      <div className="sentbar__track" onMouseLeave={() => setHover(null)}>
        {order.map((s) =>
          (pct[s] ?? 0) > 0 ? (
            <span
              key={s}
              className={`sentbar__seg sent--${s} ${hover && hover !== s ? "is-dim" : ""}`}
              style={{ flexGrow: pct[s] ?? 0 }}
              onMouseEnter={() => setHover(s)}
            />
          ) : null,
        )}
      </div>
      <div className="sentbar__caption">
        {hover ? (
          <>
            <strong>{SENTIMENT_LABEL[hover]}</strong> {pct[hover]}% · {counts[hover]} reviews
          </>
        ) : (
          <>
            <strong>{pct.positive}%</strong> positive · {pct.negative}% negative
          </>
        )}
      </div>
    </div>
  );
}

/** Monthly units as thin bars; Nov–Dec in the darker step. Hover shows the month. */
export function MonthlyBars({ months, units, height = 34 }: { months: string[]; units: number[]; height?: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(...units, 1);
  const total = units.reduce((a, b) => a + b, 0);
  return (
    <div className="bars" role="img" aria-label={`Monthly units sold, ${monthLabel(months[0])} to ${monthLabel(months[months.length - 1])}`}>
      <div className="bars__plot" style={{ height }} onMouseLeave={() => setHover(null)}>
        {units.map((u, i) => {
          const holiday = ["11", "12"].includes(months[i].slice(5, 7));
          return (
            <span key={months[i]} className="bars__hit" onMouseEnter={() => setHover(i)}>
              <span
                className={`bars__bar ${holiday ? "is-holiday" : ""} ${hover === i ? "is-hover" : ""}`}
                style={{ height: u ? `${Math.max(6, (100 * u) / max)}%` : 0 }}
              />
            </span>
          );
        })}
      </div>
      <div className="bars__caption">
        {hover != null ? (
          <>
            <strong>{monthLabel(months[hover])}</strong> · {formatNumber(units[hover])} units
          </>
        ) : total ? (
          <>
            {monthLabel(months[0])} – {monthLabel(months[months.length - 1])}
          </>
        ) : (
          "No sales"
        )}
      </div>
    </div>
  );
}

/** Five stars filled in proportion to the rating (4.45 fills 89%). */
export function Stars({ value, size = 13 }: { value: number; size?: number }) {
  const row = (className: string) => (
    <span className={`stars__row ${className}`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Star key={i} size={size} />
      ))}
    </span>
  );
  return (
    <span className="stars" role="img" aria-label={`${value} out of 5 stars`} title={`${value} / 5`}>
      {row("stars__base")}
      <span className="stars__fill" style={{ width: `${(Math.max(0, Math.min(5, value)) / 5) * 100}%` }}>
        {row("is-on")}
      </span>
    </span>
  );
}

export function SentimentBadge({ sentiment }: { sentiment: Sentiment | null }) {
  if (!sentiment) return <span className="badge badge--none">Not analysed</span>;
  const icon = { positive: "▲", neutral: "●", negative: "▼" }[sentiment];
  return (
    <span className={`badge badge--${sentiment}`}>
      <span aria-hidden="true">{icon}</span> {SENTIMENT_LABEL[sentiment]}
    </span>
  );
}
