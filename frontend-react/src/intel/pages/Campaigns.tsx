// Campaigns: list, create, import from documents, and the campaign hub page.
import { useEffect, useState, type FormEvent } from "react";
import { Bot, ClipboardList, Compass, FileSearch, Lightbulb, Plus, Save, Smile, Target, Trash2 } from "lucide-react";
import { Link, navigate } from "../../router";
import { api } from "../api";
import {
  AiStatusNotice,
  Card,
  ErrorAlert,
  KindBadge,
  Notice,
  PageHeader,
  Shell,
  StatusBadge,
  Working,
  formatDate,
  formatMoney,
  useLoad,
} from "../components";
import type { Campaign, CampaignFields, CampaignProposal, CampaignStatus } from "../types";

const STATUSES: CampaignStatus[] = ["draft", "planned", "active", "completed"];

const blank: CampaignFields = {
  name: "",
  product: "",
  objective: "",
  target_audience: "",
  positioning: "",
  key_message: "",
  budget: null,
  start_date: null,
  end_date: null,
  channels: [],
  kpis: [],
  status: "draft",
  notes: "",
};

const splitList = (value: string) => value.split(/[,\n]/).map((v) => v.trim()).filter(Boolean);

/** Create/edit form for a campaign's fields. */
function CampaignForm({
  initial,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  initial: CampaignFields;
  submitLabel: string;
  onSubmit: (fields: CampaignFields) => Promise<void>;
  onCancel?: () => void;
}) {
  const [f, setF] = useState(initial);
  const [channels, setChannels] = useState(initial.channels.join(", "));
  const [kpis, setKpis] = useState(initial.kpis.join("\n"));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    setF(initial);
    setChannels(initial.channels.join(", "));
    setKpis(initial.kpis.join("\n"));
  }, [initial]);
  const text = (key: keyof CampaignFields) => (e: { target: { value: string } }) => {
    setSaved(false);
    setF((v) => ({ ...v, [key]: e.target.value }));
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await onSubmit({ ...f, channels: splitList(channels), kpis: kpis.split("\n").map((k) => k.trim()).filter(Boolean) });
      setSaved(true);
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="form" onSubmit={submit}>
      <div className="field-row">
        <label className="field">
          <span>Campaign name *</span>
          <input className="input" required value={f.name} onChange={text("name")} maxLength={255} />
        </label>
        <label className="field">
          <span>Status</span>
          <select className="select" value={f.status} onChange={text("status")}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="field">
        <span>Product or service</span>
        <input className="input" value={f.product} onChange={text("product")} maxLength={2000} />
      </label>
      <label className="field">
        <span>Objective</span>
        <textarea className="textarea" value={f.objective} onChange={text("objective")} maxLength={4000} />
      </label>
      <label className="field">
        <span>Target audience</span>
        <textarea className="textarea" value={f.target_audience} onChange={text("target_audience")} maxLength={4000} />
      </label>
      <div className="field-row">
        <label className="field">
          <span>Positioning</span>
          <textarea className="textarea" value={f.positioning} onChange={text("positioning")} maxLength={4000} />
        </label>
        <label className="field">
          <span>Key message / USP</span>
          <textarea className="textarea" value={f.key_message} onChange={text("key_message")} maxLength={2000} />
        </label>
      </div>
      <div className="field-row">
        <label className="field">
          <span>Budget (USD)</span>
          <input
            className="input"
            type="number"
            min={0}
            step={100}
            value={f.budget ?? ""}
            onChange={(e) => setF((v) => ({ ...v, budget: e.target.value === "" ? null : Number(e.target.value) }))}
          />
        </label>
        <label className="field">
          <span>Channels (comma separated)</span>
          <input className="input" value={channels} onChange={(e) => setChannels(e.target.value)} placeholder="Instagram, Email, In-café" />
        </label>
      </div>
      <div className="field-row">
        <label className="field">
          <span>Start date</span>
          <input className="input" type="date" value={f.start_date ?? ""} onChange={(e) => setF((v) => ({ ...v, start_date: e.target.value || null }))} />
        </label>
        <label className="field">
          <span>End date</span>
          <input className="input" type="date" value={f.end_date ?? ""} min={f.start_date ?? undefined} onChange={(e) => setF((v) => ({ ...v, end_date: e.target.value || null }))} />
        </label>
      </div>
      <label className="field">
        <span>KPIs (one per line)</span>
        <textarea className="textarea" value={kpis} onChange={(e) => setKpis(e.target.value)} />
      </label>
      <label className="field">
        <span>Notes</span>
        <textarea className="textarea" value={f.notes} onChange={text("notes")} maxLength={8000} />
      </label>
      <ErrorAlert error={error} />
      <div className="page-header__actions">
        <button className="btn" disabled={saving || !f.name.trim()}>
          <Save size={15} /> {saving ? "Saving…" : submitLabel}
        </button>
        {onCancel && (
          <button type="button" className="btn btn--secondary" onClick={onCancel}>
            Cancel
          </button>
        )}
        {saved && !onCancel && <span className="small" style={{ color: "var(--ok)" }}>Saved.</span>}
      </div>
    </form>
  );
}

/** Review campaigns the AI found in the documents and save the chosen ones. */
function ImportFromDocuments({ onDone }: { onDone: () => void }) {
  const [state, setState] = useState<"loading" | "ready" | "saving">("loading");
  const [proposals, setProposals] = useState<CampaignProposal[]>([]);
  const [chosen, setChosen] = useState<Set<number>>(new Set());
  const [error, setError] = useState<unknown>(null);
  const existing = useLoad(() => api.campaigns(), []);

  useEffect(() => {
    api
      .importProposals()
      .then((r) => {
        setProposals(r.campaigns);
        setState("ready");
      })
      .catch((e) => {
        setError(e);
        setState("ready");
      });
  }, []);
  useEffect(() => {
    const names = new Set((existing.data ?? []).map((c) => c.name.toLowerCase()));
    setChosen(new Set(proposals.map((p, i) => (names.has(p.name.toLowerCase()) ? -1 : i)).filter((i) => i >= 0)));
  }, [proposals, existing.data]);

  const save = async () => {
    setState("saving");
    setError(null);
    try {
      for (const i of chosen) {
        const p = proposals[i];
        await api.createCampaign({ ...p, status: "planned", origin: "documents" });
      }
      onDone();
    } catch (e) {
      setError(e);
      setState("ready");
    }
  };

  if (state === "loading") return <Working title="Reading the marketing documents for campaigns…" steps={["Searching campaign plans", "Extracting dates, budgets and channels"]} />;
  const existingNames = new Set((existing.data ?? []).map((c) => c.name.toLowerCase()));
  return (
    <div className="stack">
      <Notice>
        <p>These campaigns were found in the company documents. Only what the documents state is filled in; check the sources, then save the ones you want.</p>
      </Notice>
      {proposals.length === 0 && !error && <p className="empty-note">No specific campaigns were found in the documents.</p>}
      <ul className="rows">
        {proposals.map((p, i) => (
          <li key={i}>
            <label className="row" style={{ cursor: "pointer", alignItems: "flex-start" }}>
              <input
                type="checkbox"
                checked={chosen.has(i)}
                onChange={(e) =>
                  setChosen((s) => {
                    const next = new Set(s);
                    if (e.target.checked) next.add(i);
                    else next.delete(i);
                    return next;
                  })
                }
                style={{ marginTop: 4, accentColor: "var(--violet)" }}
              />
              <div className="row__main">
                <div className="row__title">
                  {p.name} {existingNames.has(p.name.toLowerCase()) && <span className="badge">already added</span>}
                </div>
                <div className="small" style={{ marginTop: 2 }}>
                  {[p.product, p.budget != null ? formatMoney(p.budget) : null, p.start_date && `${p.start_date}${p.end_date ? ` → ${p.end_date}` : ""}`]
                    .filter(Boolean)
                    .join(" · ")}
                </div>
                {p.notes && <div className="muted small">{p.notes}</div>}
                <div className="muted small">Sources: {p.origin_sources.map((s) => `${s.document} p.${s.page}`).join(", ")}</div>
              </div>
            </label>
          </li>
        ))}
      </ul>
      <ErrorAlert error={error} />
      <div className="page-header__actions">
        <button className="btn" onClick={save} disabled={chosen.size === 0 || state === "saving"}>
          {state === "saving" ? "Saving…" : `Save ${chosen.size} campaign${chosen.size === 1 ? "" : "s"}`}
        </button>
        <button className="btn btn--secondary" onClick={onDone}>
          Cancel
        </button>
      </div>
    </div>
  );
}

export function CampaignsPage() {
  const campaigns = useLoad(() => api.campaigns(), []);
  const [mode, setMode] = useState<"list" | "new" | "import">("list");

  return (
    <Shell title="Campaigns">
      <PageHeader
        title="Campaigns"
        subtitle="Your marketing campaigns. Competitor, market, survey and sentiment insights link to a campaign and feed its AI strategy."
        actions={
          mode === "list" && (
            <>
              <button className="btn btn--secondary" onClick={() => setMode("import")}>
                <FileSearch size={15} /> Import from documents
              </button>
              <button className="btn" onClick={() => setMode("new")}>
                <Plus size={15} /> New campaign
              </button>
            </>
          )
        }
      />
      <div className="stack">
        {mode === "import" && <AiStatusNotice />}
        {mode === "new" && (
          <Card title="New campaign">
            <CampaignForm
              initial={blank}
              submitLabel="Create campaign"
              onCancel={() => setMode("list")}
              onSubmit={async (fields) => {
                const created = await api.createCampaign(fields);
                navigate(`/campaigns/${created.id}`);
              }}
            />
          </Card>
        )}
        {mode === "import" && (
          <Card title="Import campaigns from documents">
            <ImportFromDocuments
              onDone={() => {
                setMode("list");
                campaigns.reload();
              }}
            />
          </Card>
        )}
        <Card title={`All campaigns${campaigns.data ? ` (${campaigns.data.length})` : ""}`}>
          {campaigns.data?.length === 0 && (
            <p className="empty-note">No campaigns yet. Create one, or import the campaigns described in your marketing documents.</p>
          )}
          <ul className="rows">
            {(campaigns.data ?? []).map((c: Campaign) => (
              <li key={c.id}>
                <Link className="row" to={`/campaigns/${c.id}`}>
                  <div className="row__main">
                    <div className="row__title">{c.name}</div>
                    <div className="row__sub">
                      {[c.product, c.budget != null ? formatMoney(c.budget) : null, c.start_date ? `${formatDate(c.start_date)}${c.end_date ? ` – ${formatDate(c.end_date)}` : ""}` : null]
                        .filter(Boolean)
                        .join(" · ") || "No details yet"}
                    </div>
                  </div>
                  <div className="row__meta">
                    {c.origin === "documents" && <span className="badge" title="Imported from the marketing documents">from documents</span>}
                    <StatusBadge status={c.status} />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
          <ErrorAlert error={campaigns.error} />
        </Card>
      </div>
    </Shell>
  );
}

const MODULES = [
  { kind: "competitor", label: "Competitor analysis", to: "/competitors", icon: Target },
  { kind: "research", label: "Market research", to: "/research", icon: Compass },
  { kind: "survey", label: "Survey", to: "/surveys", icon: ClipboardList },
  { kind: "sentiment", label: "Sentiment analysis", to: "/sentiment", icon: Smile },
] as const;

export function CampaignDetailPage({ id }: { id: string }) {
  const detail = useLoad(() => api.campaign(id), [id]);
  const c = detail.data;

  const remove = async () => {
    if (!c || !window.confirm(`Delete “${c.name}”? Its analyses and surveys are kept but unlinked.`)) return;
    await api.deleteCampaign(c.id);
    navigate("/campaigns");
  };

  return (
    <Shell title={c?.name ?? "Campaign"}>
      <PageHeader
        back={{ to: "/campaigns", label: "All campaigns" }}
        title={c?.name ?? "Campaign"}
        subtitle={
          c && (
            <>
              <StatusBadge status={c.status} /> {c.product && <> · {c.product}</>}
              {c.budget != null && <> · {formatMoney(c.budget)}</>}
              {c.start_date && <> · {formatDate(c.start_date)}{c.end_date && ` – ${formatDate(c.end_date)}`}</>}
            </>
          )
        }
        actions={
          c && (
            <>
              <Link className="btn btn--secondary" to={`/ai-team?campaign=${c.id}`}>
                <Bot size={15} /> Ask the AI team
              </Link>
              <Link className="btn" to={`/strategy?campaign=${c.id}`}>
                <Lightbulb size={15} /> Generate strategy
              </Link>
            </>
          )
        }
      />
      <ErrorAlert error={detail.error} />
      {c && (
        <div className="split" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(0, 400px)" }}>
          <div className="stack">
            <Card title="Campaign details" subtitle="Strategies can fill these for you with “Apply to campaign”.">
              <CampaignForm
                initial={c}
                submitLabel="Save changes"
                onSubmit={async (fields) => {
                  await api.updateCampaign(c.id, fields);
                  detail.reload();
                }}
              />
            </Card>
            {c.origin === "documents" && c.origin_sources.length > 0 && (
              <Card title="Imported from documents">
                <ul className="point-list">
                  {c.origin_sources.map((s) => (
                    <li key={s.id}>
                      {s.document}, page {s.page}
                      {s.section && ` · ${s.section}`}
                    </li>
                  ))}
                </ul>
              </Card>
            )}
            <button className="btn btn--danger" style={{ alignSelf: "flex-start" }} onClick={remove}>
              <Trash2 size={15} /> Delete campaign
            </button>
          </div>
          <div className="stack">
            <Card title="Insights for this campaign" subtitle="Feed the AI strategy and appear in the campaign's reports.">
              <ul className="rows">
                {MODULES.map(({ kind, label, to, icon: Icon }) => {
                  const items = kind === "survey" ? c.surveys : c.analyses.filter((a) => a.kind === kind);
                  return (
                    <li key={kind}>
                      <div className="row">
                        <Icon size={18} style={{ color: "var(--violet)", flexShrink: 0 }} />
                        <div className="row__main">
                          <div className="row__title">{label}</div>
                          <div className="row__sub">{items.length ? `${items.length} saved` : "None yet"}</div>
                        </div>
                        <Link className="btn btn--secondary btn--small" to={`${to}?campaign=${c.id}`}>
                          {items.length ? "Add" : "Run"}
                        </Link>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </Card>
            <Card title="Saved analyses">
              {c.analyses.length === 0 ? (
                <p className="empty-note">No analyses linked yet.</p>
              ) : (
                <ul className="rows">
                  {c.analyses.map((a) => (
                    <li key={a.id}>
                      <Link className="row" to={`/insights/${a.id}`}>
                        <div className="row__main">
                          <div className="row__title">{a.title}</div>
                          <div className="row__sub">
                            {formatDate(a.created_at)} · {a.summary}
                          </div>
                        </div>
                        <KindBadge kind={a.kind} />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            <Card title="Surveys">
              {c.surveys.length === 0 ? (
                <p className="empty-note">
                  No surveys. <Link to={`/surveys?campaign=${c.id}`}>Create one</Link> to hear from customers.
                </p>
              ) : (
                <ul className="rows">
                  {c.surveys.map((s) => (
                    <li key={s.id}>
                      <Link className="row" to={`/surveys/${s.id}`}>
                        <div className="row__main">
                          <div className="row__title">{s.title}</div>
                          <div className="row__sub">{s.response_count} real responses</div>
                        </div>
                        <StatusBadge status={s.status} />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </div>
      )}
    </Shell>
  );
}
