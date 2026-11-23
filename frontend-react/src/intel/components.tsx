// Shared building blocks for the marketing intelligence pages.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { AlertTriangle, ArrowLeft, Download, FileText, Globe, Info, Menu, Trash2 } from "lucide-react";
import { checkHealth, fetchDocuments } from "../api";
import { Sidebar, type BackendStatus } from "../components/Sidebar";
import { Link, navigate } from "../router";
import type { DocumentInfo } from "../types";
import { api, reportUrl } from "./api";
import type { AiStatus, Analysis, Campaign, EvidenceItem, Point, Recommendation } from "./types";

// ---------- Data loading ----------

/** Load data on mount / when deps change; `reload` refetches. */
export function useLoad<T>(load: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const counter = useRef(0);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(load, deps);
  const reload = useCallback(() => {
    const ticket = ++counter.current;
    setLoading(true);
    run()
      .then((value) => ticket === counter.current && (setData(value), setError(null)))
      .catch((e: Error) => ticket === counter.current && setError(e))
      .finally(() => ticket === counter.current && setLoading(false));
  }, [run]);
  useEffect(reload, [reload]);
  return { data, error, loading, reload, setData };
}

let statusPromise: Promise<AiStatus> | null = null;
export function useAiStatus(): AiStatus | null {
  const [status, setStatus] = useState<AiStatus | null>(null);
  useEffect(() => {
    statusPromise ??= api.status().catch((e) => {
      statusPromise = null;
      throw e;
    });
    statusPromise.then(setStatus).catch(() => setStatus(null));
  }, []);
  return status;
}

export function useCampaigns() {
  return useLoad(() => api.campaigns(), []);
}

// ---------- Formatting ----------

export const formatDate = (iso: string | null | undefined, withTime = false) =>
  iso
    ? new Date(iso).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
      })
    : "—";

export const formatMoney = (value: number | null | undefined) =>
  value == null ? "—" : value.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export const KIND_LABEL: Record<string, string> = {
  competitor: "Competitor analysis",
  research: "Market research",
  sentiment: "Sentiment analysis",
  survey: "Survey analysis",
  strategy: "Marketing strategy",
};

// ---------- Layout ----------

function useBackend() {
  const [status, setStatus] = useState<BackendStatus>("checking");
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      const ok = await checkHealth().catch(() => false);
      if (cancelled) return;
      setStatus(ok ? "online" : "offline");
      if (ok) fetchDocuments().then((d) => !cancelled && setDocuments(d)).catch(() => {});
    };
    poll();
    const timer = setInterval(poll, 20000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);
  return { status, documents };
}

/** App frame for module pages: sidebar, top bar and a scrolling page body. */
export function Shell({ title, children }: { title: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const { status, documents } = useBackend();
  useEffect(() => {
    document.title = `${title} · MarketMind`;
  }, [title]);
  return (
    <div className="app">
      <Sidebar open={open} documents={documents} status={status} onClose={() => setOpen(false)} />
      {open && <div className="scrim" onClick={() => setOpen(false)} />}
      <main className="main">
        <header className="topbar">
          <button className="icon-btn topbar__menu" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu size={20} />
          </button>
          <div className="topbar__title">{title}</div>
        </header>
        <div className="scroll">
          <div className="page">{children}</div>
        </div>
      </main>
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
  back,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  back?: { to: string; label: string };
}) {
  return (
    <>
      {back && (
        <Link className="back-link" to={back.to}>
          <ArrowLeft size={14} /> {back.label}
        </Link>
      )}
      <div className="page-header">
        <div>
          <h1>{title}</h1>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {actions && <div className="page-header__actions">{actions}</div>}
      </div>
    </>
  );
}

export function Card({ title, subtitle, actions, children, className = "" }: {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card__head">
          <div>
            {title && <h2 className="card__title">{title}</h2>}
            {subtitle && <p className="card__subtitle">{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

// ---------- Feedback ----------

export function ErrorAlert({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="alert alert--error" role="alert">
      <AlertTriangle size={16} />
      <p>{message}</p>
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warn"; children: ReactNode }) {
  return (
    <div className={`alert alert--${tone}`}>
      {tone === "warn" ? <AlertTriangle size={16} /> : <Info size={16} />}
      <div>{children}</div>
    </div>
  );
}

/** Shown while an agent runs: a spinner, elapsed time and the steps it goes through. */
export function Working({ title, steps = [] }: { title: string; steps?: string[] }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  // Advance through the listed steps on a rough schedule; it is an estimate, not real progress.
  const current = Math.min(steps.length - 1, Math.floor(seconds / 4));
  return (
    <div className="working" role="status" aria-live="polite">
      <div className="spinner" />
      <div className="working__title">{title}</div>
      <div className="small">{seconds}s elapsed · this usually takes 10–40 seconds</div>
      {steps.length > 0 && (
        <ol className="progress-steps">
          {steps.map((step, i) => (
            <li key={step} className={i < current ? "is-done" : i === current ? "is-current" : ""}>
              {i < current ? "✓" : i === current ? <span className="spinner spinner--small" /> : "○"} {step}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

/** Warns when Azure OpenAI is missing; explains live research status when relevant. */
export function AiStatusNotice({ research = false }: { research?: boolean }) {
  const status = useAiStatus();
  if (!status) return null;
  if (!status.ai_configured) {
    return (
      <Notice tone="warn">
        <p>
          <strong>Azure OpenAI is not configured.</strong> Set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY and
          AZURE_OPENAI_CHAT_DEPLOYMENT in <code>.env</code> and restart the API to use the AI features.
        </p>
      </Notice>
    );
  }
  if (research && !status.web_search.configured) {
    return (
      <Notice tone="warn">
        <p>
          <strong>Live web research is not configured.</strong> Results use the company documents and the details you
          enter, and every report says so. Add <code>BRAVE_SEARCH_API_KEY</code> to <code>.env</code> to enable Brave
          Search.
        </p>
      </Notice>
    );
  }
  return null;
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge badge--${status}`}>{status}</span>;
}

export function LiveBadge({ live }: { live: boolean }) {
  return live ? (
    <span className="badge badge--live" title="Live web search results were used">
      <Globe size={11} /> Live web research
    </span>
  ) : (
    <span className="badge badge--nolive" title="No live web search was performed">
      No live web research
    </span>
  );
}

// ---------- Citations & evidence ----------

const EvidenceContext = createContext<Map<string, EvidenceItem>>(new Map());

export function EvidenceProvider({ evidence, children }: { evidence: EvidenceItem[]; children: ReactNode }) {
  return <EvidenceContext.Provider value={new Map(evidence.map((e) => [e.id, e]))}>{children}</EvidenceContext.Provider>;
}

function describeEvidence(item: EvidenceItem): string {
  if (item.kind === "document") return `${item.document}, page ${item.page}${item.section ? ` · ${item.section}` : ""}`;
  if (item.kind === "web") return item.url ?? "web";
  if (item.kind === "analysis") return "Saved analysis";
  return "Supplied by you";
}

export function Cite({ ids }: { ids: string[] }) {
  const evidence = useContext(EvidenceContext);
  if (!ids.length) return null;
  const jump = (id: string) => {
    const target = document.getElementById(`ev-${id}`);
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.classList.remove("is-flash");
    void target.offsetWidth;
    target.classList.add("is-flash");
  };
  return (
    <>
      {ids.map((id) => {
        const item = evidence.get(id);
        return (
          <button
            key={id}
            type="button"
            className="cite-btn"
            title={item ? `${item.title} — ${describeEvidence(item)}` : id}
            onClick={() => jump(id)}
          >
            {id}
          </button>
        );
      })}
    </>
  );
}

export function InferenceBadge() {
  return (
    <span className="badge badge--inference" title="Not backed by a cited source — AI inference">
      AI inference
    </span>
  );
}

/** A claim with citations, or an "AI inference" badge when it has none. */
export function Claim({ point }: { point: Point }) {
  return (
    <>
      {point.text} {point.sources.length ? <Cite ids={point.sources} /> : point.verified === false && <InferenceBadge />}
    </>
  );
}

export function Points({ points, empty = "None identified." }: { points: Point[]; empty?: string }) {
  if (!points?.length) return <p className="muted small">{empty}</p>;
  return (
    <ul className="point-list">
      {points.map((p, i) => (
        <li key={i}>
          <Claim point={p} />
        </li>
      ))}
    </ul>
  );
}

export function Recommendations({ items }: { items: Recommendation[] }) {
  if (!items?.length) return <p className="muted small">No recommendations.</p>;
  return (
    <ul className="point-list">
      {items.map((r, i) => (
        <li key={i}>
          <strong>{r.action}</strong> <span className={`badge badge--${r.priority}`}>{r.priority}</span>
          <div className="muted small">
            {r.rationale} {r.sources?.length ? <Cite ids={r.sources} /> : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

export function EvidenceList({ evidence, live, research }: { evidence: EvidenceItem[]; live: boolean; research: boolean }) {
  return (
    <Card
      title="Sources"
      subtitle={
        research
          ? live
            ? "Live web results were retrieved for this analysis."
            : "No live web research was performed: findings use company documents and information you supplied."
          : "Evidence used for this analysis."
      }
      actions={research ? <LiveBadge live={live} /> : undefined}
    >
      {evidence.length === 0 ? (
        <p className="muted small">No external sources were used.</p>
      ) : (
        <ol className="evidence">
          {evidence.map((e) => (
            <li key={e.id} id={`ev-${e.id}`}>
              <span className="evidence__id">{e.id}</span>
              <div>
                <div>
                  <strong>{e.title}</strong>
                </div>
                <div className="evidence__meta">
                  {e.kind === "web" && e.url ? (
                    <a href={e.url} target="_blank" rel="noreferrer noopener">
                      {e.url}
                    </a>
                  ) : e.kind === "analysis" && e.url ? (
                    <Link to={e.url}>Open saved analysis</Link>
                  ) : (
                    describeEvidence(e)
                  )}
                  {" · retrieved "}
                  {formatDate(e.retrieved_at)}
                  {e.published ? ` · published ${e.published}` : ""}
                </div>
                <div className="evidence__text">{e.text.length > 320 ? `${e.text.slice(0, 320)}…` : e.text}</div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

// ---------- Actions ----------

export function ReportActions({ analysis, onDeleted }: { analysis: Analysis; onDeleted?: () => void }) {
  const remove = async () => {
    if (!window.confirm(`Delete “${analysis.title}”? This cannot be undone.`)) return;
    await api.deleteAnalysis(analysis.id);
    onDeleted ? onDeleted() : navigate("/dashboard");
  };
  return (
    <>
      <a className="btn btn--secondary btn--small" href={reportUrl(analysis.id, "pdf")} download>
        <Download size={14} /> PDF
      </a>
      <a className="btn btn--secondary btn--small" href={reportUrl(analysis.id, "md")} download>
        <FileText size={14} /> Markdown
      </a>
      <button className="btn btn--danger btn--small" onClick={remove}>
        <Trash2 size={14} /> Delete
      </button>
    </>
  );
}

export function CampaignSelect({
  value,
  onChange,
  campaigns,
  label = "Link to campaign",
  optional = true,
}: {
  value: string;
  onChange: (id: string) => void;
  campaigns: Campaign[] | null;
  label?: string;
  optional?: boolean;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select className="select" value={value} onChange={(e) => onChange(e.target.value)}>
        {optional && <option value="">No campaign</option>}
        {!optional && !value && <option value="">Choose a campaign…</option>}
        {(campaigns ?? []).map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
      {campaigns && campaigns.length === 0 && (
        <small>
          No campaigns yet — <Link to="/campaigns">create one</Link> to connect insights to it.
        </small>
      )}
    </label>
  );
}

export function KindBadge({ kind }: { kind: string }) {
  return <span className="badge badge--kind">{KIND_LABEL[kind] ?? kind}</span>;
}
