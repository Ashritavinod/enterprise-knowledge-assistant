// Dashboard, standalone insight page and the AI Team (supervisor) chat.
import { useRef, useState, type FormEvent } from "react";
import { Bot, ClipboardList, Compass, Lightbulb, Megaphone, Send, Smile, Square, Target } from "lucide-react";
import { RichText } from "../../components/RichText";
import { Link, navigate } from "../../router";
import { agentChat, api } from "../api";
import {
  AiStatusNotice,
  Card,
  CampaignSelect,
  ErrorAlert,
  KindBadge,
  PageHeader,
  Shell,
  StatusBadge,
  formatDate,
  formatMoney,
  useAiStatus,
  useCampaigns,
  useLoad,
} from "../components";
import type { AgentStep } from "../types";
import { AnalysisView } from "../views";

const MODULES = [
  { to: "/campaigns", label: "Campaigns", text: "Plan campaigns and connect every insight to them.", icon: Megaphone },
  { to: "/competitors", label: "Competitor Intelligence", text: "Comparison tables, SWOT and differentiation.", icon: Target },
  { to: "/surveys", label: "AI Survey Studio", text: "Draft, publish and analyse customer surveys.", icon: ClipboardList },
  { to: "/sentiment", label: "Customer Sentiment", text: "Classify reviews and feedback, find themes.", icon: Smile },
  { to: "/research", label: "Market Research", text: "Trends, needs, segments and opportunities.", icon: Compass },
  { to: "/strategy", label: "AI Marketing Strategy", text: "A full strategy from your insights.", icon: Lightbulb },
];

export function DashboardPage() {
  const status = useAiStatus();
  const campaigns = useLoad(() => api.campaigns(), []);
  const analyses = useLoad(() => api.analyses({ limit: 200 }), []);
  const surveys = useLoad(() => api.surveys(), []);
  const live = (campaigns.data ?? []).filter((c) => c.status === "active" || c.status === "planned").length;
  const responses = (surveys.data ?? []).reduce((sum, s) => sum + s.response_count, 0);
  const published = (surveys.data ?? []).filter((s) => s.status === "published").length;

  return (
    <Shell title="Dashboard">
      <PageHeader
        title="Marketing intelligence"
        subtitle={`${status?.company ?? "Your company"}'s campaigns, research and customer insights in one place.`}
        actions={
          <Link className="btn" to="/ai-team">
            <Bot size={15} /> Ask the AI team
          </Link>
        }
      />
      <div className="stack">
        <AiStatusNotice research />
        <div className="stat-grid">
          <div className="stat">
            <div className="stat__label">Campaigns</div>
            <div className="stat__value">{campaigns.data?.length ?? "—"}</div>
            <div className="stat__sub">{live} planned or active</div>
          </div>
          <div className="stat">
            <div className="stat__label">Saved insights</div>
            <div className="stat__value">{analyses.data?.length ?? "—"}</div>
            <div className="stat__sub">analyses and strategies</div>
          </div>
          <div className="stat">
            <div className="stat__label">Surveys</div>
            <div className="stat__value">{surveys.data?.length ?? "—"}</div>
            <div className="stat__sub">{published} collecting responses</div>
          </div>
          <div className="stat">
            <div className="stat__label">Real survey responses</div>
            <div className="stat__value">{surveys.data ? responses.toLocaleString() : "—"}</div>
            <div className="stat__sub">from customers via survey links</div>
          </div>
        </div>
        <div className="grid-2">
          <Card title="Recent insights" actions={<span className="muted small">{analyses.data?.length ?? 0} total</span>}>
            {analyses.data?.length === 0 && <p className="empty-note">No insights yet. Run a module below to create one.</p>}
            <ul className="rows">
              {(analyses.data ?? []).slice(0, 8).map((a) => (
                <li key={a.id}>
                  <Link className="row" to={`/insights/${a.id}`}>
                    <div className="row__main">
                      <div className="row__title">{a.title}</div>
                      <div className="row__sub">
                        {formatDate(a.created_at)}
                        {a.campaign_name ? ` · ${a.campaign_name}` : ""} · {a.summary}
                      </div>
                    </div>
                    <KindBadge kind={a.kind} />
                  </Link>
                </li>
              ))}
            </ul>
            <ErrorAlert error={analyses.error} />
          </Card>
          <Card title="Campaigns" actions={<Link className="link-btn" to="/campaigns">View all</Link>}>
            {campaigns.data?.length === 0 && (
              <p className="empty-note">
                No campaigns yet. <Link to="/campaigns">Create one or import them from your documents.</Link>
              </p>
            )}
            <ul className="rows">
              {(campaigns.data ?? []).slice(0, 8).map((c) => (
                <li key={c.id}>
                  <Link className="row" to={`/campaigns/${c.id}`}>
                    <div className="row__main">
                      <div className="row__title">{c.name}</div>
                      <div className="row__sub">
                        {[c.product, c.budget != null ? formatMoney(c.budget) : null, c.start_date ? formatDate(c.start_date) : null].filter(Boolean).join(" · ") || "No details yet"}
                      </div>
                    </div>
                    <StatusBadge status={c.status} />
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        </div>
        <div className="grid-3">
          {MODULES.map(({ to, label, text, icon: Icon }) => (
            <Link key={to} to={to} className="card" style={{ textDecoration: "none", color: "inherit" }}>
              <Icon size={22} style={{ color: "var(--violet)" }} />
              <div className="card__title" style={{ marginTop: 10 }}>
                {label}
              </div>
              <p className="card__subtitle">{text}</p>
            </Link>
          ))}
        </div>
      </div>
    </Shell>
  );
}

export function InsightPage({ id }: { id: string }) {
  const analysis = useLoad(() => api.analysis(id), [id]);
  return (
    <Shell title={analysis.data?.title ?? "Insight"}>
      <PageHeader back={{ to: "/dashboard", label: "Dashboard" }} title={analysis.data?.title ?? "Insight"} />
      <ErrorAlert error={analysis.error} />
      {analysis.data && <AnalysisView analysis={analysis.data} onDeleted={() => navigate("/dashboard")} onApplied={analysis.reload} />}
    </Shell>
  );
}

// ---------- AI team ----------

interface Turn {
  role: "user" | "assistant";
  text: string;
  steps: AgentStep[];
  error?: string;
  pending?: boolean;
}

const EXAMPLES = [
  "What are our brand colours and when do we use each?",
  "Compare us with Sweetwell Patisserie and Frostline Cupcakes for this campaign.",
  "Draft a survey to test price points for the Summer Scoops gelato with parents.",
  "Using everything saved for this campaign, build the marketing strategy.",
];

const STEP_LINK: Record<string, string> = {
  competitor: "/competitors",
  research: "/research",
  sentiment: "/sentiment",
  survey: "/insights",
  strategy: "/strategy",
};

export function AiTeamPage() {
  const status = useAiStatus();
  const campaigns = useCampaigns();
  const [campaignId, setCampaignId] = useState(new URLSearchParams(window.location.search).get("campaign") ?? "");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [message, setMessage] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const busy = turns.some((t) => t.pending);

  const updateLast = (change: (t: Turn) => Turn) => setTurns((all) => [...all.slice(0, -1), change(all[all.length - 1])]);

  const send = async (text: string) => {
    if (!text.trim() || busy) return;
    const history = turns.filter((t) => !t.error && t.text).map((t) => ({ role: t.role, content: t.text }));
    setTurns((all) => [...all, { role: "user", text, steps: [] }, { role: "assistant", text: "", steps: [], pending: true }]);
    setMessage("");
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await agentChat(
        { message: text, campaign_id: campaignId || null, history },
        (event) => {
          if (event.type === "step") {
            updateLast((t) => ({ ...t, steps: [...t.steps.filter((s) => s.id !== event.id), event].sort((a, b) => a.id - b.id) }));
          } else if (event.type === "answer") {
            updateLast((t) => ({ ...t, text: event.text }));
          } else {
            updateLast((t) => ({ ...t, error: event.message }));
          }
        },
        controller.signal,
      );
    } catch (error) {
      updateLast((t) => ({ ...t, error: controller.signal.aborted ? "Stopped." : (error as Error).message }));
    } finally {
      updateLast((t) => ({ ...t, pending: false }));
      abortRef.current = null;
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    send(message);
  };

  return (
    <Shell title="AI Team">
      <PageHeader
        title="AI marketing team"
        subtitle="A supervisor agent reads your request and brings in the Competitor, Market Research, Survey, Sentiment and Strategy agents only when needed. Their results are saved so you can open them."
      />
      <div className="stack">
        <AiStatusNotice />
        <Card>
          <CampaignSelect value={campaignId} onChange={setCampaignId} campaigns={campaigns.data} label="Working on campaign (results are linked to it)" />
        </Card>
        {turns.length === 0 && (
          <div className="grid-2">
            {EXAMPLES.map((example) => (
              <button key={example} className="card" style={{ textAlign: "left", cursor: "pointer" }} onClick={() => send(example)} disabled={status?.ai_configured === false}>
                <span className="prose">{example}</span>
              </button>
            ))}
          </div>
        )}
        <div className="team-thread" aria-live="polite">
          {turns.map((turn, i) =>
            turn.role === "user" ? (
              <div key={i} className="team-msg team-msg--user">
                <div className="team-bubble">{turn.text}</div>
              </div>
            ) : (
              <div key={i} className="team-msg">
                {turn.steps.length > 0 && (
                  <ol className="team-steps" aria-label="Agent steps">
                    {turn.steps.map((step) => (
                      <li key={step.id} className={step.status === "error" ? "is-error" : ""}>
                        {step.status === "running" ? <span className="spinner spinner--small" /> : step.status === "done" ? "✓" : "✕"}
                        <span className="agent">{step.agent}</span>
                        <span>{step.detail}</span>
                        {step.analysis_id && step.kind && (
                          <Link className="link-btn" to={step.kind === "survey" ? `/insights/${step.analysis_id}` : `${STEP_LINK[step.kind]}/${step.analysis_id}`}>
                            Open result
                          </Link>
                        )}
                        {step.survey_id && (
                          <Link className="link-btn" to={`/surveys/${step.survey_id}`}>
                            Open survey draft
                          </Link>
                        )}
                      </li>
                    ))}
                  </ol>
                )}
                {turn.pending && !turn.text && (
                  <div className="team-bubble muted">
                    <span className="spinner spinner--small" style={{ display: "inline-block", verticalAlign: -2, marginRight: 8 }} />
                    {turn.steps.length ? "Specialists at work…" : "Thinking…"}
                  </div>
                )}
                {turn.text && (
                  <div className="team-bubble">
                    <RichText text={turn.text} />
                  </div>
                )}
                {turn.error && <ErrorAlert error={new Error(turn.error)} />}
              </div>
            ),
          )}
        </div>
        <form className="team-composer" onSubmit={submit}>
          <textarea
            className="textarea"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(message);
              }
            }}
            placeholder="Ask the AI team… (Enter to send, Shift+Enter for a new line)"
            maxLength={4000}
            aria-label="Message to the AI team"
          />
          {busy ? (
            <button type="button" className="btn btn--secondary" onClick={() => abortRef.current?.abort()}>
              <Square size={15} /> Stop
            </button>
          ) : (
            <button className="btn" disabled={!message.trim() || status?.ai_configured === false}>
              <Send size={15} /> Send
            </button>
          )}
        </form>
      </div>
    </Shell>
  );
}
