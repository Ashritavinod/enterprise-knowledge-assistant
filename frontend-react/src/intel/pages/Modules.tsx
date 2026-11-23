// Competitor Intelligence, Market Research, Customer Sentiment and Strategy pages.
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Plus, Sparkles, Trash2, Upload } from "lucide-react";
import { Link, navigate } from "../../router";
import { api } from "../api";
import {
  AiStatusNotice,
  Card,
  CampaignSelect,
  ErrorAlert,
  KIND_LABEL,
  Notice,
  PageHeader,
  Shell,
  Working,
  formatDate,
  useAiStatus,
  useCampaigns,
  useLoad,
} from "../components";
import type { Analysis, AnalysisKind, CampaignDetail, SurveySummary } from "../types";
import { AnalysisView } from "../views";

const queryCampaign = () => new URLSearchParams(window.location.search).get("campaign") ?? "";

/** Runs an agent request with loading and error state. */
function useRun() {
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const run = async (fn: () => Promise<Analysis>, base: string) => {
    setRunning(true);
    setError(null);
    try {
      const created = await fn();
      navigate(`${base}/${created.id}`);
    } catch (e) {
      setError(e);
    } finally {
      setRunning(false);
    }
  };
  return { running, error, run };
}

/** Shared layout: form + history on top, the selected analysis below. */
function ModulePage({
  kind,
  base,
  title,
  subtitle,
  research = false,
  id,
  form,
  workingTitle,
  workingSteps,
  running,
}: {
  kind: AnalysisKind;
  base: string;
  title: string;
  subtitle: string;
  research?: boolean;
  id?: string;
  form: ReactNode;
  workingTitle: string;
  workingSteps: string[];
  running: boolean;
}) {
  const history = useLoad(() => api.analyses({ kind, limit: 30 }), [kind, id]);
  const selected = useLoad(() => (id ? api.analysis(id) : Promise.resolve(null)), [id]);
  useEffect(() => {
    if (id) document.getElementById("result")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [id, selected.data]);

  return (
    <Shell title={title}>
      <PageHeader title={title} subtitle={subtitle} />
      <div className="stack">
        <AiStatusNotice research={research} />
        <div className="split">
          <Card title="New analysis">{form}</Card>
          <Card title="Previous analyses" subtitle={`${KIND_LABEL[kind]}s saved in the app`}>
            {history.loading && !history.data ? (
              <p className="muted small">Loading…</p>
            ) : history.data?.length ? (
              <ul className="rows" style={{ maxHeight: 460, overflowY: "auto" }}>
                {history.data.map((a) => (
                  <li key={a.id}>
                    <Link className="row" to={`${base}/${a.id}`} aria-current={a.id === id ? "page" : undefined}>
                      <div className="row__main">
                        <div className="row__title" style={a.id === id ? { color: "var(--violet)" } : undefined}>
                          {a.title}
                        </div>
                        <div className="row__sub">
                          {formatDate(a.created_at, true)}
                          {a.campaign_name ? ` · ${a.campaign_name}` : ""} · {a.summary}
                        </div>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="empty-note">Nothing yet. Run your first analysis with the form.</p>
            )}
            <ErrorAlert error={history.error} />
          </Card>
        </div>
        <div id="result" style={{ scrollMarginTop: 16 }}>
          {running ? (
            <Card>
              <Working title={workingTitle} steps={workingSteps} />
            </Card>
          ) : id ? (
            selected.data ? (
              <AnalysisView analysis={selected.data} onDeleted={() => navigate(base)} />
            ) : selected.error ? (
              <ErrorAlert error={selected.error} />
            ) : (
              <p className="muted">Loading analysis…</p>
            )
          ) : null}
        </div>
      </div>
    </Shell>
  );
}

// ---------- Competitor intelligence ----------

interface CompetitorRow {
  name: string;
  website: string;
  notes: string;
}

export function CompetitorPage({ id }: { id?: string }) {
  const status = useAiStatus();
  const campaigns = useCampaigns();
  const { running, error, run } = useRun();
  const [rows, setRows] = useState<CompetitorRow[]>([{ name: "", website: "", notes: "" }]);
  const [industry, setIndustry] = useState("");
  const [company, setCompany] = useState("");
  const [useWeb, setUseWeb] = useState(true);
  const [campaignId, setCampaignId] = useState(queryCampaign);
  const webReady = !!status?.web_search.configured;

  const update = (i: number, patch: Partial<CompetitorRow>) =>
    setRows((all) => all.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const valid = rows.some((r) => r.name.trim());

  const submit = (e: FormEvent) => {
    e.preventDefault();
    run(
      () =>
        api.competitors({
          competitors: rows.filter((r) => r.name.trim()),
          industry,
          company,
          use_web: useWeb && webReady,
          campaign_id: campaignId || null,
        }),
      "/competitors",
    );
  };

  return (
    <ModulePage
      kind="competitor"
      base="/competitors"
      title="Competitor Intelligence"
      subtitle="Compare competitors' products, pricing, features and marketing; get a SWOT analysis, market gaps and differentiation ideas. Every fact cites its source."
      research
      id={id}
      running={running}
      workingTitle="Competitor Intelligence Agent is researching…"
      workingSteps={["Reading company documents", webReady && useWeb ? "Searching the web" : "Using your competitor notes", "Comparing competitors", "Writing SWOT and recommendations"]}
      form={
        <form className="form" onSubmit={submit}>
          {rows.map((row, i) => (
            <div key={i} className="repeat-row">
              <input className="input" placeholder={`Competitor ${i + 1} name`} value={row.name} onChange={(e) => update(i, { name: e.target.value })} aria-label={`Competitor ${i + 1} name`} maxLength={200} />
              <input className="input" placeholder="Website (optional)" value={row.website} onChange={(e) => update(i, { website: e.target.value })} aria-label={`Competitor ${i + 1} website`} maxLength={500} />
              <button type="button" className="icon-btn" onClick={() => setRows((all) => all.filter((_, j) => j !== i))} disabled={rows.length === 1} aria-label={`Remove competitor ${i + 1}`}>
                <Trash2 size={16} />
              </button>
              <textarea className="textarea" placeholder="What you know: products, prices you've seen, campaigns… (optional, cited as your input)" value={row.notes} onChange={(e) => update(i, { notes: e.target.value })} aria-label={`Competitor ${i + 1} notes`} maxLength={4000} />
            </div>
          ))}
          {rows.length < 6 && (
            <button type="button" className="btn btn--secondary btn--small" onClick={() => setRows((all) => [...all, { name: "", website: "", notes: "" }])}>
              <Plus size={14} /> Add competitor
            </button>
          )}
          <div className="field-row">
            <label className="field">
              <span>Industry</span>
              <input className="input" value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder="e.g. bakery cafés" maxLength={300} />
            </label>
            <label className="field">
              <span>Your company</span>
              <input className="input" value={company} onChange={(e) => setCompany(e.target.value)} placeholder={status?.company ?? ""} maxLength={200} />
            </label>
          </div>
          <CampaignSelect value={campaignId} onChange={setCampaignId} campaigns={campaigns.data} />
          <label className="check">
            <input type="checkbox" checked={useWeb && webReady} disabled={!webReady} onChange={(e) => setUseWeb(e.target.checked)} />
            <span>
              Use live web research (Brave Search)
              {!webReady && <span className="muted small"> — not configured</span>}
            </span>
          </label>
          <ErrorAlert error={error} />
          <button className="btn" disabled={!valid || running || status?.ai_configured === false}>
            <Sparkles size={16} /> {running ? "Analysing…" : "Analyse competitors"}
          </button>
        </form>
      }
    />
  );
}

// ---------- Market research ----------

export function ResearchPage({ id }: { id?: string }) {
  const status = useAiStatus();
  const campaigns = useCampaigns();
  const { running, error, run } = useRun();
  const [form, setForm] = useState({ industry: "", audience: "", products: "", market_notes: "" });
  const [useWeb, setUseWeb] = useState(true);
  const [campaignId, setCampaignId] = useState(queryCampaign);
  const webReady = !!status?.web_search.configured;
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    run(() => api.research({ ...form, use_web: useWeb && webReady, campaign_id: campaignId || null }), "/research");
  };

  return (
    <ModulePage
      kind="research"
      base="/research"
      title="Market Research"
      subtitle="Find trends, customer needs, underserved segments and opportunities. Verified findings are kept separate from AI hypotheses."
      research
      id={id}
      running={running}
      workingTitle="Market Research Agent is working…"
      workingSteps={["Reading company documents", webReady && useWeb ? "Searching the web" : "Using your market notes", "Identifying trends and needs", "Separating verified findings from hypotheses"]}
      form={
        <form className="form" onSubmit={submit}>
          <label className="field">
            <span>Industry / market</span>
            <input className="input" value={form.industry} onChange={set("industry")} placeholder="e.g. bakery cafés and desserts" maxLength={300} />
          </label>
          <label className="field">
            <span>Target audience</span>
            <input className="input" value={form.audience} onChange={set("audience")} placeholder="e.g. families on the US West Coast" maxLength={1000} />
          </label>
          <label className="field">
            <span>Products or services</span>
            <input className="input" value={form.products} onChange={set("products")} placeholder="e.g. gelato, celebration cakes" maxLength={1000} />
          </label>
          <label className="field">
            <span>Market information you have (optional)</span>
            <textarea className="textarea" value={form.market_notes} onChange={set("market_notes")} placeholder="Reports, figures or observations; cited as your input" maxLength={8000} />
          </label>
          <CampaignSelect value={campaignId} onChange={setCampaignId} campaigns={campaigns.data} />
          <label className="check">
            <input type="checkbox" checked={useWeb && webReady} disabled={!webReady} onChange={(e) => setUseWeb(e.target.checked)} />
            <span>
              Use live web research (Brave Search)
              {!webReady && <span className="muted small"> — not configured</span>}
            </span>
          </label>
          <ErrorAlert error={error} />
          <button className="btn" disabled={running || !(form.industry || form.audience || form.products) || status?.ai_configured === false}>
            <Sparkles size={16} /> {running ? "Researching…" : "Research the market"}
          </button>
        </form>
      }
    />
  );
}

// ---------- Customer sentiment ----------

/** Header row of a CSV (handles quoted names). */
function csvHeader(text: string): string[] {
  const line = text.split(/\r?\n/, 1)[0] ?? "";
  const cells: string[] = [];
  let current = "";
  let quoted = false;
  for (const ch of line) {
    if (ch === '"') quoted = !quoted;
    else if (ch === "," && !quoted) {
      cells.push(current.trim());
      current = "";
    } else current += ch;
  }
  cells.push(current.trim());
  return cells.filter(Boolean);
}

export function SentimentPage({ id }: { id?: string }) {
  const status = useAiStatus();
  const campaigns = useCampaigns();
  const { running, error, run } = useRun();
  const [source, setSource] = useState<"paste" | "csv" | "survey">("paste");
  const [text, setText] = useState("");
  const [csv, setCsv] = useState<{ name: string; text: string; columns: string[] } | null>(null);
  const [column, setColumn] = useState("");
  const [surveyId, setSurveyId] = useState("");
  const [surveyTexts, setSurveyTexts] = useState<string[] | null>(null);
  const [campaignId, setCampaignId] = useState(queryCampaign);
  const [title, setTitle] = useState("");
  const [localError, setLocalError] = useState<unknown>(null);
  const surveys = useLoad(() => api.surveys(), []);

  const lines = useMemo(() => text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean), [text]);

  useEffect(() => {
    setSurveyTexts(null);
    if (!surveyId) return;
    api
      .surveyResults(surveyId)
      .then((r) => setSurveyTexts(r.questions.filter((q) => q.type === "open_ended").flatMap((q) => q.answers ?? [])))
      .catch(setLocalError);
  }, [surveyId]);

  const readFile = (file: File | undefined) => {
    setLocalError(null);
    if (!file) return;
    if (file.size > 2_500_000) {
      setLocalError(new Error("That file is over 2.5 MB. Split it or keep only the feedback column."));
      return;
    }
    file.text().then((content) => {
      setCsv({ name: file.name, text: content, columns: csvHeader(content) });
      setColumn("");
    });
  };

  const count = source === "paste" ? lines.length : source === "survey" ? surveyTexts?.length ?? 0 : null;
  const ready = source === "paste" ? lines.length > 0 : source === "csv" ? !!csv : (surveyTexts?.length ?? 0) > 0;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const base = { campaign_id: campaignId || null, title };
    const body =
      source === "csv"
        ? { ...base, source: "csv", csv_text: csv!.text, csv_column: column }
        : { ...base, source: source === "survey" ? "survey" : "paste", texts: source === "survey" ? surveyTexts : lines };
    run(() => api.sentiment(body), "/sentiment");
  };

  return (
    <ModulePage
      kind="sentiment"
      base="/sentiment"
      title="Customer Sentiment Analysis"
      subtitle="Classify reviews, survey answers and feedback as positive, neutral or negative; find recurring topics, complaints and expectations; get improvement recommendations."
      id={id}
      running={running}
      workingTitle="Sentiment Analysis Agent is reading the feedback…"
      workingSteps={["Classifying each item", "Counting topics", "Summarising complaints and expectations", "Writing recommendations"]}
      form={
        <form className="form" onSubmit={submit}>
          <div className="tabs" role="tablist" aria-label="Feedback source">
            {(
              [
                ["paste", "Paste text"],
                ["csv", "Upload CSV"],
                ["survey", "From a survey"],
              ] as const
            ).map(([key, label]) => (
              <button key={key} type="button" role="tab" aria-selected={source === key} className={`tab ${source === key ? "is-active" : ""}`} onClick={() => setSource(key)}>
                {label}
              </button>
            ))}
          </div>
          {source === "paste" && (
            <label className="field">
              <span>Feedback — one review or comment per line</span>
              <textarea className="textarea" style={{ minHeight: 160 }} value={text} onChange={(e) => setText(e.target.value)} placeholder={"The croissants are always fresh!\nWaited 20 minutes for my app order."} />
              <small>{lines.length} item{lines.length === 1 ? "" : "s"} (up to 500)</small>
            </label>
          )}
          {source === "csv" && (
            <>
              <label className="btn btn--secondary" style={{ cursor: "pointer" }}>
                <Upload size={15} /> {csv ? csv.name : "Choose a CSV file"}
                <input type="file" accept=".csv,text/csv" hidden onChange={(e) => readFile(e.target.files?.[0])} />
              </label>
              {csv && (
                <label className="field">
                  <span>Column with the feedback text</span>
                  <select className="select" value={column} onChange={(e) => setColumn(e.target.value)}>
                    <option value="">Detect automatically</option>
                    {csv.columns.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                  <small>The first 500 non-empty rows are analysed.</small>
                </label>
              )}
            </>
          )}
          {source === "survey" && (
            <label className="field">
              <span>Survey</span>
              <select className="select" value={surveyId} onChange={(e) => setSurveyId(e.target.value)}>
                <option value="">Choose a survey…</option>
                {(surveys.data ?? []).filter((s: SurveySummary) => s.response_count > 0).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title} ({s.response_count} responses)
                  </option>
                ))}
              </select>
              <small>
                {surveyId
                  ? surveyTexts === null
                    ? "Loading answers…"
                    : `${surveyTexts.length} open-ended answers from real respondents`
                  : "Uses the open-ended answers from real responses."}
              </small>
            </label>
          )}
          <CampaignSelect value={campaignId} onChange={setCampaignId} campaigns={campaigns.data} />
          <label className="field">
            <span>Title (optional)</span>
            <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Google reviews, May 2026" maxLength={255} />
          </label>
          <ErrorAlert error={error || localError} />
          <button className="btn" disabled={!ready || running || status?.ai_configured === false}>
            <Sparkles size={16} /> {running ? "Analysing…" : count ? `Analyse ${count} item${count === 1 ? "" : "s"}` : "Analyse feedback"}
          </button>
        </form>
      }
    />
  );
}

// ---------- Strategy ----------

export function StrategyPage({ id }: { id?: string }) {
  const status = useAiStatus();
  const campaigns = useCampaigns();
  const { running, error, run } = useRun();
  const [campaignId, setCampaignId] = useState(queryCampaign);
  const [detail, setDetail] = useState<CampaignDetail | null>(null);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [notes, setNotes] = useState("");

  useEffect(() => {
    setDetail(null);
    if (!campaignId) return;
    api.campaign(campaignId).then((d) => {
      setDetail(d);
      // Default: the latest analysis of each insight kind.
      const latest = new Map<string, string>();
      for (const a of d.analyses) if (a.kind !== "strategy" && !latest.has(a.kind)) latest.set(a.kind, a.id);
      setChosen(new Set(latest.values()));
    });
  }, [campaignId]);

  const insights = detail?.analyses.filter((a) => a.kind !== "strategy") ?? [];
  const missing = (["competitor", "research", "survey", "sentiment"] as const).filter((k) => !insights.some((a) => a.kind === k));
  const moduleFor: Record<string, string> = { competitor: "/competitors", research: "/research", survey: "/surveys", sentiment: "/sentiment" };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    run(() => api.strategy({ campaign_id: campaignId, analysis_ids: [...chosen], notes }), "/strategy");
  };

  return (
    <ModulePage
      kind="strategy"
      base="/strategy"
      title="AI Marketing Strategy"
      subtitle="Combine a campaign with its competitor, market, survey and sentiment insights into a complete strategy you can download and apply to the campaign."
      id={id}
      running={running}
      workingTitle="Marketing Strategy Agent is building the plan…"
      workingSteps={["Reading the campaign and its insights", "Checking brand and channel rules", "Defining audience, positioning and USP", "Planning channels, timeline and KPIs"]}
      form={
        <form className="form" onSubmit={submit}>
          <CampaignSelect value={campaignId} onChange={setCampaignId} campaigns={campaigns.data} label="Campaign" optional={false} />
          {detail && (
            <div className="field">
              <span>Insights to use</span>
              {insights.length === 0 && <small>No saved insights for this campaign yet.</small>}
              {insights.map((a) => (
                <label key={a.id} className="check">
                  <input
                    type="checkbox"
                    checked={chosen.has(a.id)}
                    onChange={(e) =>
                      setChosen((s) => {
                        const next = new Set(s);
                        if (e.target.checked) next.add(a.id);
                        else next.delete(a.id);
                        return next;
                      })
                    }
                  />
                  <span>
                    <strong>{KIND_LABEL[a.kind]}</strong> · {a.title} <span className="muted small">({formatDate(a.created_at)})</span>
                  </span>
                </label>
              ))}
              {missing.length > 0 && (
                <Notice tone="warn">
                  <p>
                    Missing: {missing.map((k, i) => (
                      <span key={k}>
                        {i > 0 && ", "}
                        <Link to={`${moduleFor[k]}?campaign=${campaignId}`}>{KIND_LABEL[k].toLowerCase()}</Link>
                      </span>
                    ))}
                    . The strategy will note what still needs research.
                  </p>
                </Notice>
              )}
            </div>
          )}
          <label className="field">
            <span>Notes for the strategist (optional)</span>
            <textarea className="textarea" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Constraints, priorities, must-haves…" maxLength={4000} />
          </label>
          <ErrorAlert error={error} />
          <button className="btn" disabled={!campaignId || running || status?.ai_configured === false}>
            <Sparkles size={16} /> {running ? "Generating…" : "Generate strategy"}
          </button>
        </form>
      }
    />
  );
}
