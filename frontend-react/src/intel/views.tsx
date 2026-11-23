// Renders saved analyses: one view per kind, shared by module pages and /insights/:id.
import { useState } from "react";
import { CheckCircle2, ExternalLink } from "lucide-react";
import { Link } from "../router";
import { api } from "./api";
import { BarList, RatingColumns, SentimentSplit, TopicBars } from "./charts";
import {
  Card,
  Cite,
  Claim,
  ErrorAlert,
  EvidenceList,
  EvidenceProvider,
  KindBadge,
  LiveBadge,
  Notice,
  Points,
  Recommendations,
  ReportActions,
  formatDate,
  formatMoney,
} from "./components";
import type { Analysis, Point, SentimentResult, SurveyResults } from "./types";

// ---------- Competitor ----------

const ASPECTS = [
  ["products_services", "Products & services"],
  ["pricing", "Pricing"],
  ["features", "Features"],
  ["marketing_strategy", "Marketing"],
  ["positioning", "Positioning"],
] as const;

function CompetitorView({ a }: { a: Analysis }) {
  const r = a.result;
  const swot: [string, string, Point[]][] = [
    ["s", "Strengths", r.swot.strengths],
    ["w", "Weaknesses", r.swot.weaknesses],
    ["o", "Opportunities", r.swot.opportunities],
    ["t", "Threats", r.swot.threats],
  ];
  return (
    <>
      <Card title="Summary">
        <p className="prose">{r.summary}</p>
      </Card>
      <Card title="Comparison" subtitle="Every cell cites its source; “Not found” means the evidence didn't say.">
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Company</th>
                {ASPECTS.map(([, label]) => (
                  <th key={label}>{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {r.comparison.map((row: any) => (
                <tr key={row.competitor}>
                  <td>{row.competitor}</td>
                  {ASPECTS.map(([key]) => (
                    <td key={key}>
                      <Claim point={row[key]} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Card title="SWOT analysis" subtitle={`For ${a.input.company ?? "your company"} relative to these competitors`}>
        <div className="swot">
          {swot.map(([key, label, points]) => (
            <div key={key} className={`swot__cell swot__cell--${key}`}>
              <h4>{label}</h4>
              <Points points={points} />
            </div>
          ))}
        </div>
      </Card>
      <div className="grid-2">
        {r.competitor_profiles.map((p: any) => (
          <Card key={p.competitor} title={p.competitor}>
            <div className="section-title">Strengths</div>
            <Points points={p.strengths} />
            <div className="section-title" style={{ marginTop: 14 }}>
              Weaknesses
            </div>
            <Points points={p.weaknesses} />
          </Card>
        ))}
      </div>
      <div className="grid-2">
        <Card title="Market gaps">
          <Points points={r.market_gaps} />
        </Card>
        <Card title="Differentiation opportunities">
          <Points points={r.differentiation} />
        </Card>
      </div>
      <Card title="Recommendations">
        <Recommendations items={r.recommendations} />
      </Card>
      {r.data_limitations?.length > 0 && (
        <Notice tone="warn">
          <strong>Data limitations</strong>
          <ul className="point-list" style={{ marginTop: 6 }}>
            {r.data_limitations.map((d: string, i: number) => (
              <li key={i}>{d}</li>
            ))}
          </ul>
        </Notice>
      )}
    </>
  );
}

// ---------- Market research ----------

function ResearchView({ a }: { a: Analysis }) {
  const r = a.result;
  return (
    <>
      <Card title="Summary">
        <p className="prose">{r.summary}</p>
      </Card>
      <Card title="Verified findings" subtitle="Stated in the cited sources" actions={<span className="badge badge--verified">Verified</span>}>
        <Points points={r.verified_findings} empty="No findings could be verified from the available sources." />
      </Card>
      <div className="grid-2">
        <Card title="Emerging trends">
          <Points points={r.trends} />
        </Card>
        <Card title="Customer needs">
          <Points points={r.customer_needs} />
        </Card>
      </div>
      <Card title="Underserved segments">
        <ul className="point-list">
          {r.underserved_segments.map((s: any, i: number) => (
            <li key={i}>
              <strong>{s.segment}</strong> — {s.description}{" "}
              {s.sources.length ? <Cite ids={s.sources} /> : <span className="badge badge--inference">AI inference</span>}
            </li>
          ))}
        </ul>
      </Card>
      <Card title="Opportunities">
        <ul className="point-list">
          {r.opportunities.map((o: any, i: number) => (
            <li key={i}>
              <strong>{o.title}</strong> <span className={`badge badge--${o.confidence}`}>{o.confidence} confidence</span>
              <div className="muted small">
                {o.description}{" "}
                {o.sources.length ? <Cite ids={o.sources} /> : <span className="badge badge--inference">AI inference</span>}
              </div>
            </li>
          ))}
        </ul>
      </Card>
      <div className="grid-2">
        <Card title="Product and service gaps">
          <Points points={r.product_gaps} />
        </Card>
        <Card title="Hypotheses to validate" subtitle="AI-generated, not supported by the sources" actions={<span className="badge badge--inference">AI hypotheses</span>}>
          <ul className="point-list">
            {r.hypotheses.map((h: any, i: number) => (
              <li key={i}>
                {h.text}
                <div className="muted small">
                  {h.rationale}
                  {h.how_to_validate && <> · Validate: {h.how_to_validate}</>}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
      <Card title="Recommendations">
        <Recommendations items={r.recommendations} />
      </Card>
      {r.data_limitations?.length > 0 && (
        <Notice tone="warn">
          <strong>Data limitations</strong>
          <ul className="point-list" style={{ marginTop: 6 }}>
            {r.data_limitations.map((d: string, i: number) => (
              <li key={i}>{d}</li>
            ))}
          </ul>
        </Notice>
      )}
    </>
  );
}

// ---------- Sentiment ----------

export function SentimentBody({ r }: { r: SentimentResult }) {
  const [filter, setFilter] = useState<"all" | "positive" | "neutral" | "negative">("all");
  const items = r.items.filter((i) => filter === "all" || i.sentiment === filter);
  return (
    <>
      <div className="stat-grid">
        <div className="stat">
          <div className="stat__label">Feedback analysed</div>
          <div className="stat__value">{r.stats.total.toLocaleString()}</div>
        </div>
        <div className="stat">
          <div className="stat__label">Positive</div>
          <div className="stat__value">{r.stats.percentages.positive}%</div>
          <div className="stat__sub">{r.stats.counts.positive} items</div>
        </div>
        <div className="stat">
          <div className="stat__label">Negative</div>
          <div className="stat__value">{r.stats.percentages.negative}%</div>
          <div className="stat__sub">{r.stats.counts.negative} items</div>
        </div>
        <div className="stat">
          <div className="stat__label">Satisfaction</div>
          <div className="stat__value" style={{ textTransform: "capitalize" }}>
            {r.summary.satisfaction_level}
          </div>
          <div className="stat__sub">Net score {r.stats.net_score > 0 ? "+" : ""}{r.stats.net_score} (−100 to +100)</div>
        </div>
      </div>
      <Card title="Sentiment split" subtitle="Share of feedback items by overall sentiment">
        <SentimentSplit stats={r.stats} />
      </Card>
      <Card title="Recurring topics" subtitle="Mentions per topic, split by sentiment">
        <TopicBars topics={r.stats.topics} />
      </Card>
      <Card title="Summary">
        <p className="prose">{r.summary.overall_summary}</p>
      </Card>
      <div className="grid-2">
        <Card title="Top complaints">
          <ul className="point-list">
            {r.summary.complaints.map((c, i) => (
              <li key={i}>
                <strong>{c.issue}</strong>
                <div className="muted small">“{c.example}”</div>
              </li>
            ))}
          </ul>
          {r.summary.complaints.length === 0 && <p className="muted small">No recurring complaints.</p>}
        </Card>
        <Card title="What customers expect">
          <ul className="point-list">
            {r.summary.expectations.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </Card>
        <Card title="Strengths">
          <ul className="point-list">
            {r.summary.strengths.map((s, i) => (
              <li key={i}>{s.text}</li>
            ))}
          </ul>
        </Card>
        <Card title="Weaknesses">
          <ul className="point-list">
            {r.summary.weaknesses.map((w, i) => (
              <li key={i}>{w.text}</li>
            ))}
          </ul>
        </Card>
      </div>
      <Card title="Recommended improvements" subtitle="Based on the feedback above">
        <Recommendations items={r.summary.recommendations} />
      </Card>
      <Card
        title="Classified feedback"
        subtitle="Each item as the AI labelled it"
        actions={
          <div className="tabs" role="tablist">
            {(["all", "positive", "neutral", "negative"] as const).map((f) => (
              <button key={f} role="tab" aria-selected={filter === f} className={`tab ${filter === f ? "is-active" : ""}`} onClick={() => setFilter(f)}>
                {f === "all" ? `All (${r.items.length})` : `${f[0].toUpperCase()}${f.slice(1)} (${r.stats.counts[f]})`}
              </button>
            ))}
          </div>
        }
      >
        <div className="table-scroll" style={{ maxHeight: 420, overflowY: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Feedback</th>
                <th>Sentiment</th>
                <th>Topics</th>
                <th className="num">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.index}>
                  <td style={{ fontWeight: 400 }}>{i.text}</td>
                  <td style={{ textTransform: "capitalize" }}>{i.sentiment}</td>
                  <td>{i.topics.join(", ")}</td>
                  <td className="num">{Math.round(i.confidence * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

// ---------- Survey ----------

export function SurveyResultsBody({ stats }: { stats: SurveyResults }) {
  return (
    <>
      {stats.questions.map((q) => (
        <Card key={q.id} title={q.text} subtitle={`${q.answered} of ${stats.total_responses} answered`}>
          {q.type === "multiple_choice" && q.options && (
            <BarList rows={q.options.map((o) => ({ label: o.option, value: o.percent, display: `${o.percent}% (${o.count})` }))} />
          )}
          {q.type === "rating" && q.distribution && (
            <>
              <p className="small" style={{ margin: "0 0 4px" }}>
                Average <strong>{q.average ?? "—"}</strong> on a {q.scale_min}–{q.scale_max} scale
              </p>
              <RatingColumns distribution={q.distribution} minLabel={q.scale_min_label} maxLabel={q.scale_max_label} />
            </>
          )}
          {q.type === "open_ended" && (
            <ul className="point-list" style={{ maxHeight: 240, overflowY: "auto" }}>
              {(q.answers ?? []).map((answer, i) => (
                <li key={i}>“{answer}”</li>
              ))}
              {!q.answers?.length && <li className="muted">No answers yet.</li>}
            </ul>
          )}
        </Card>
      ))}
    </>
  );
}

function SurveyAnalysisView({ a }: { a: Analysis }) {
  const r = a.result;
  const ins = r.insights;
  return (
    <>
      <Notice tone={r.small_sample ? "warn" : "info"}>
        <p>
          Based on <strong>{r.stats.total_responses} real responses</strong> collected through the survey link. No sample or
          synthetic responses are included.
          {r.small_sample && " This is a small sample: treat percentages as indicative only."}
        </p>
      </Notice>
      <Card title="Summary">
        <p className="prose">{ins.summary}</p>
      </Card>
      <Card title="Key findings">
        <ul className="point-list">
          {ins.key_findings.map((f: any, i: number) => (
            <li key={i}>
              {f.finding} <span className="muted small">({f.question_ids.join(", ")})</span>
            </li>
          ))}
        </ul>
      </Card>
      <div className="grid-2">
        <Card title="Customer preferences">
          <ul className="point-list">
            {ins.preferences.map((p: string, i: number) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </Card>
        <Card title="Customer expectations">
          <ul className="point-list">
            {ins.expectations.map((p: string, i: number) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </Card>
      </div>
      <Card title="Recommendations">
        <Recommendations items={ins.recommendations} />
      </Card>
      {ins.caveats.length > 0 && (
        <Notice tone="warn">
          <strong>Caveats</strong>
          <ul className="point-list" style={{ marginTop: 6 }}>
            {ins.caveats.map((c: string, i: number) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </Notice>
      )}
      <h2 className="section-title" style={{ marginTop: 8 }}>
        Results by question
      </h2>
      <SurveyResultsBody stats={r.stats} />
      {r.open_ended_sentiment && (
        <>
          <h2 className="section-title" style={{ marginTop: 8 }}>
            Sentiment of open-ended answers
          </h2>
          <SentimentBody r={r.open_ended_sentiment} />
        </>
      )}
    </>
  );
}

// ---------- Strategy ----------

function StrategyView({ a, onApplied }: { a: Analysis; onApplied?: () => void }) {
  const r = a.result;
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState<string[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const apply = async () => {
    if (!a.campaign_id) return;
    if (!window.confirm("Fill the campaign's positioning, key message, audience, objectives, channels and KPIs from this strategy?")) return;
    setApplying(true);
    setError(null);
    try {
      const result = await api.applyStrategy(a.campaign_id, a.id);
      setApplied(result.applied_fields);
      onApplied?.();
    } catch (e) {
      setError(e);
    } finally {
      setApplying(false);
    }
  };
  return (
    <>
      {a.campaign_id && (
        <Card
          title="Use this strategy in the campaign"
          subtitle="Copies positioning, USP (as key message), audience, objectives, channels and KPIs onto the campaign."
          actions={
            <button className="btn btn--small" onClick={apply} disabled={applying}>
              {applying ? "Applying…" : "Apply to campaign"}
            </button>
          }
        >
          {applied && (
            <p className="small" style={{ margin: 0, color: "var(--ok)" }}>
              <CheckCircle2 size={14} style={{ verticalAlign: -2 }} /> Applied: {applied.join(", ")}.{" "}
              <Link to={`/campaigns/${a.campaign_id}`}>Open the campaign</Link>
            </p>
          )}
          <ErrorAlert error={error} />
        </Card>
      )}
      {r.insight_gaps?.length > 0 && (
        <Notice tone="warn">
          <p>
            No saved {r.insight_gaps.join(", ")} analysis was available for this campaign, so those parts rely on the documents
            only. Run those modules and regenerate for a stronger strategy.
          </p>
        </Notice>
      )}
      <Card title="Executive summary">
        <p className="prose">{r.executive_summary}</p>
      </Card>
      <div className="grid-2">
        <Card title="Positioning">
          <p className="prose">
            <Claim point={r.positioning} />
          </p>
        </Card>
        <Card title="Unique selling proposition">
          <p className="prose">
            <Claim point={r.usp} />
          </p>
        </Card>
      </div>
      <Card title="Target audience">
        <ul className="point-list">
          {r.target_audience.map((t: any, i: number) => (
            <li key={i}>
              <strong>{t.segment}</strong> — {t.description}
              <div className="muted small">
                {t.rationale} <Cite ids={t.sources} />
              </div>
            </li>
          ))}
        </ul>
      </Card>
      <Card title="Customer segmentation">
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Segment</th>
                <th>Needs</th>
                <th>Message</th>
                <th>Priority</th>
              </tr>
            </thead>
            <tbody>
              {r.segmentation.map((s: any, i: number) => (
                <tr key={i}>
                  <td>{s.segment}</td>
                  <td>{s.needs}</td>
                  <td>
                    {s.message} <Cite ids={s.sources} />
                  </td>
                  <td>
                    <span className={`badge badge--${s.priority}`}>{s.priority}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Card title="Campaign objectives">
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Objective</th>
                <th>Metric</th>
                <th>Target</th>
              </tr>
            </thead>
            <tbody>
              {r.objectives.map((o: any, i: number) => (
                <tr key={i}>
                  <td>
                    {o.objective} <Cite ids={o.sources} />
                  </td>
                  <td>{o.metric}</td>
                  <td>{o.target}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Card title="Recommended channels" subtitle={r.channels.some((c: any) => c.budget_share_percent != null) ? "Share of the campaign budget" : undefined}>
        {r.channels.some((c: any) => c.budget_share_percent != null) && (
          <div style={{ marginBottom: 14 }}>
            <BarList
              rows={r.channels.map((c: any) => ({
                label: c.channel,
                value: c.budget_share_percent ?? 0,
                display: `${c.budget_share_percent ?? 0}%${c.budget_amount != null ? ` · ${formatMoney(c.budget_amount)}` : ""}`,
              }))}
            />
          </div>
        )}
        {r.budget_note && <p className="muted small">{r.budget_note}</p>}
        <ul className="point-list">
          {r.channels.map((c: any, i: number) => (
            <li key={i}>
              <strong>{c.channel}</strong> — {c.role}
              <div className="muted small">
                {c.rationale} <Cite ids={c.sources} />
              </div>
            </li>
          ))}
        </ul>
      </Card>
      <div className="grid-2">
        <Card title="Content ideas">
          <ul className="point-list">
            {r.content_ideas.map((c: any, i: number) => (
              <li key={i}>
                {c.idea} <span className="muted small">· {c.channel} · {c.format}</span>
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Promotions">
          <Points points={r.promotions} />
        </Card>
      </div>
      <Card title="Competitor differentiation">
        <Points points={r.differentiation} />
      </Card>
      <Card title="Timeline">
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Phase</th>
                <th>Dates</th>
                <th>Activities</th>
              </tr>
            </thead>
            <tbody>
              {r.timeline.map((t: any, i: number) => (
                <tr key={i}>
                  <td>{t.phase}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {t.start} – {t.end}
                  </td>
                  <td>{t.activities.map((s: string) => s.replace(/[.;]\s*$/, "")).join(" · ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <div className="grid-2">
        <Card title="Action plan">
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Step</th>
                  <th>Owner</th>
                  <th>Due</th>
                </tr>
              </thead>
              <tbody>
                {r.action_plan.map((s: any, i: number) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 400 }}>{s.step}</td>
                    <td>{s.owner}</td>
                    <td style={{ whiteSpace: "nowrap" }}>{s.due}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card title="KPIs and measurement">
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>KPI</th>
                  <th>Target</th>
                  <th>How to measure</th>
                </tr>
              </thead>
              <tbody>
                {r.kpis.map((k: any, i: number) => (
                  <tr key={i}>
                    <td>{k.kpi}</td>
                    <td>{k.target}</td>
                    <td style={{ fontWeight: 400 }}>{k.measurement}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
      <Card title="Risks">
        <Points points={r.risks} />
      </Card>
    </>
  );
}

// ---------- Dispatcher ----------

const RESEARCH_KINDS = new Set(["competitor", "research"]);

/** Header (title, badges, downloads) and body for any saved analysis. */
export function AnalysisView({ analysis, onDeleted, onApplied }: { analysis: Analysis; onDeleted?: () => void; onApplied?: () => void }) {
  const a = analysis;
  return (
    <EvidenceProvider evidence={a.evidence}>
      <div className="stack">
        <Card
          title={a.title}
          subtitle={
            <>
              {formatDate(a.created_at, true)}
              {a.campaign_name && (
                <>
                  {" · campaign "}
                  <Link to={`/campaigns/${a.campaign_id}`}>{a.campaign_name}</Link>
                </>
              )}
              {a.model && ` · ${a.model}`}
            </>
          }
          actions={
            <div className="page-header__actions">
              <KindBadge kind={a.kind} />
              {RESEARCH_KINDS.has(a.kind) && <LiveBadge live={a.live_research} />}
              <ReportActions analysis={a} onDeleted={onDeleted} />
              <Link className="btn btn--secondary btn--small" to={`/insights/${a.id}`} title="Open as a standalone page">
                <ExternalLink size={14} />
              </Link>
            </div>
          }
        >
          {a.kind === "survey" && a.survey_id && (
            <p className="small" style={{ margin: 0 }}>
              From survey <Link to={`/surveys/${a.survey_id}`}>{a.input.survey_title ?? "responses"}</Link> ·{" "}
              {a.input.responses_analysed} responses analysed
            </p>
          )}
          {a.kind === "sentiment" && (
            <p className="small muted" style={{ margin: 0 }}>
              Source: {a.input.source}
              {a.input.csv_column ? ` (CSV column “${a.input.csv_column}”)` : ""} · {a.input.item_count} items
            </p>
          )}
        </Card>
        {a.kind === "competitor" && <CompetitorView a={a} />}
        {a.kind === "research" && <ResearchView a={a} />}
        {a.kind === "sentiment" && <SentimentBody r={a.result} />}
        {a.kind === "survey" && <SurveyAnalysisView a={a} />}
        {a.kind === "strategy" && <StrategyView a={a} onApplied={onApplied} />}
        {a.kind !== "sentiment" && a.kind !== "survey" && (
          <EvidenceList evidence={a.evidence} live={a.live_research} research={RESEARCH_KINDS.has(a.kind)} />
        )}
      </div>
    </EvidenceProvider>
  );
}
