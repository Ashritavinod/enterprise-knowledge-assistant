// AI Survey Studio: generate, edit, publish, share, collect real responses, analyse.
import { useEffect, useState, type FormEvent } from "react";
import { ArrowDown, ArrowUp, Check, Copy, Download, Lock, Plus, Send, Sparkles, Trash2 } from "lucide-react";
import { LogoMark } from "../../components/Logo";
import { Link, navigate } from "../../router";
import { api, publicSurveyUrl, responsesCsvUrl } from "../api";
import {
  AiStatusNotice,
  Card,
  CampaignSelect,
  ErrorAlert,
  Notice,
  PageHeader,
  Shell,
  StatusBadge,
  Working,
  formatDate,
  useAiStatus,
  useCampaigns,
  useLoad,
} from "../components";
import type { Analysis, QuestionType, Survey, SurveyQuestion } from "../types";
import { AnalysisView, SurveyResultsBody } from "../views";

const TYPE_LABEL: Record<QuestionType, string> = {
  multiple_choice: "Multiple choice",
  rating: "Rating scale",
  open_ended: "Open-ended",
};

export function SurveysPage() {
  const status = useAiStatus();
  const campaigns = useCampaigns();
  const surveys = useLoad(() => api.surveys(), []);
  const [form, setForm] = useState({ product: "", objective: "", audience: "", question_count: 8 });
  const [campaignId, setCampaignId] = useState(new URLSearchParams(window.location.search).get("campaign") ?? "");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const set = (key: "product" | "objective" | "audience") => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setRunning(true);
    setError(null);
    try {
      const survey = await api.generateSurvey({ ...form, campaign_id: campaignId || null });
      navigate(`/surveys/${survey.id}`);
    } catch (err) {
      setError(err);
      setRunning(false);
    }
  };

  return (
    <Shell title="AI Survey Studio">
      <PageHeader
        title="AI Survey Studio"
        subtitle="Let AI draft a survey, edit it, publish it with a shareable link, and analyse the real responses you collect."
      />
      <div className="stack">
        <AiStatusNotice />
        <div className="split">
          <Card title="Generate a survey">
            {running ? (
              <Working title="Survey Agent is drafting questions…" steps={["Reading product context", "Writing questions", "Balancing question types"]} />
            ) : (
              <form className="form" onSubmit={submit}>
                <label className="field">
                  <span>Product, service or campaign *</span>
                  <input className="input" required value={form.product} onChange={set("product")} placeholder="e.g. Summer Scoops gelato" maxLength={1000} />
                </label>
                <label className="field">
                  <span>Business objective *</span>
                  <input className="input" required value={form.objective} onChange={set("objective")} placeholder="e.g. Choose flavours and a price point" maxLength={1000} />
                </label>
                <label className="field">
                  <span>Target audience *</span>
                  <input className="input" required value={form.audience} onChange={set("audience")} placeholder="e.g. Parents who visit our cafés" maxLength={1000} />
                </label>
                <label className="field">
                  <span>Number of questions</span>
                  <input className="input" type="number" min={3} max={15} value={form.question_count} onChange={(e) => setForm((f) => ({ ...f, question_count: Math.max(3, Math.min(15, Number(e.target.value) || 8)) }))} />
                </label>
                <CampaignSelect value={campaignId} onChange={setCampaignId} campaigns={campaigns.data} />
                <ErrorAlert error={error} />
                <button className="btn" disabled={status?.ai_configured === false}>
                  <Sparkles size={16} /> Generate draft
                </button>
              </form>
            )}
          </Card>
          <Card title="Your surveys">
            {surveys.data?.length === 0 && <p className="empty-note">No surveys yet.</p>}
            <ul className="rows">
              {(surveys.data ?? []).map((s) => (
                <li key={s.id}>
                  <Link className="row" to={`/surveys/${s.id}`}>
                    <div className="row__main">
                      <div className="row__title">{s.title}</div>
                      <div className="row__sub">
                        {s.response_count} real response{s.response_count === 1 ? "" : "s"} · created {formatDate(s.created_at)}
                      </div>
                    </div>
                    <StatusBadge status={s.status} />
                  </Link>
                </li>
              ))}
            </ul>
            <ErrorAlert error={surveys.error} />
          </Card>
        </div>
      </div>
    </Shell>
  );
}

// ---------- Editor ----------

function newQuestion(type: QuestionType): SurveyQuestion {
  return {
    id: "",
    type,
    text: "",
    options: type === "multiple_choice" ? ["Option 1", "Option 2"] : [],
    allow_multiple: false,
    scale_min: type === "rating" ? 1 : null,
    scale_max: type === "rating" ? 5 : null,
    scale_min_label: type === "rating" ? "Not at all" : "",
    scale_max_label: type === "rating" ? "Very much" : "",
    required: true,
  };
}

function QuestionEditor({
  q,
  index,
  total,
  onChange,
  onMove,
  onRemove,
}: {
  q: SurveyQuestion;
  index: number;
  total: number;
  onChange: (q: SurveyQuestion) => void;
  onMove: (delta: number) => void;
  onRemove: () => void;
}) {
  const set = (patch: Partial<SurveyQuestion>) => onChange({ ...q, ...patch });
  return (
    <div className="q-card">
      <div className="q-card__head">
        <span className="q-card__num">Q{index + 1}</span>
        <select className="select" style={{ width: "auto" }} value={q.type} onChange={(e) => onChange({ ...newQuestion(e.target.value as QuestionType), text: q.text, id: q.id })} aria-label="Question type">
          {(Object.keys(TYPE_LABEL) as QuestionType[]).map((t) => (
            <option key={t} value={t}>
              {TYPE_LABEL[t]}
            </option>
          ))}
        </select>
        <label className="check">
          <input type="checkbox" checked={q.required} onChange={(e) => set({ required: e.target.checked })} /> Required
        </label>
        <span style={{ flex: 1 }} />
        <button type="button" className="icon-btn" onClick={() => onMove(-1)} disabled={index === 0} aria-label="Move up">
          <ArrowUp size={16} />
        </button>
        <button type="button" className="icon-btn" onClick={() => onMove(1)} disabled={index === total - 1} aria-label="Move down">
          <ArrowDown size={16} />
        </button>
        <button type="button" className="icon-btn" onClick={onRemove} disabled={total === 1} aria-label="Delete question">
          <Trash2 size={16} />
        </button>
      </div>
      <textarea className="textarea" style={{ minHeight: 54 }} value={q.text} onChange={(e) => set({ text: e.target.value })} placeholder="Question text" maxLength={500} aria-label={`Question ${index + 1} text`} />
      {q.type === "multiple_choice" && (
        <div className="q-options">
          {q.options.map((option, i) => (
            <div key={i} className="q-option">
              <input className="input" value={option} onChange={(e) => set({ options: q.options.map((o, j) => (j === i ? e.target.value : o)) })} aria-label={`Option ${i + 1}`} maxLength={200} />
              <button type="button" className="icon-btn" onClick={() => set({ options: q.options.filter((_, j) => j !== i) })} disabled={q.options.length <= 2} aria-label={`Remove option ${i + 1}`}>
                <Trash2 size={15} />
              </button>
            </div>
          ))}
          <div className="page-header__actions">
            {q.options.length < 12 && (
              <button type="button" className="btn btn--secondary btn--small" onClick={() => set({ options: [...q.options, `Option ${q.options.length + 1}`] })}>
                <Plus size={13} /> Option
              </button>
            )}
            <label className="check">
              <input type="checkbox" checked={q.allow_multiple} onChange={(e) => set({ allow_multiple: e.target.checked })} /> Allow several answers
            </label>
          </div>
        </div>
      )}
      {q.type === "rating" && (
        <div className="field-row">
          <label className="field">
            <span>Scale</span>
            <select className="select" value={`${q.scale_min}-${q.scale_max}`} onChange={(e) => { const [a, b] = e.target.value.split("-").map(Number); set({ scale_min: a, scale_max: b }); }}>
              <option value="1-5">1 – 5</option>
              <option value="1-7">1 – 7</option>
              <option value="0-10">0 – 10</option>
            </select>
          </label>
          <div className="field-row">
            <label className="field">
              <span>Low label</span>
              <input className="input" value={q.scale_min_label} onChange={(e) => set({ scale_min_label: e.target.value })} maxLength={60} />
            </label>
            <label className="field">
              <span>High label</span>
              <input className="input" value={q.scale_max_label} onChange={(e) => set({ scale_max_label: e.target.value })} maxLength={60} />
            </label>
          </div>
        </div>
      )}
    </div>
  );
}

function ShareLink({ id }: { id: string }) {
  const [copied, setCopied] = useState(false);
  const url = publicSurveyUrl(id);
  return (
    <div className="share-box">
      <code>{url}</code>
      <button
        className="btn btn--secondary btn--small"
        onClick={() =>
          navigator.clipboard.writeText(url).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          })
        }
      >
        {copied ? <Check size={14} /> : <Copy size={14} />} {copied ? "Copied" : "Copy link"}
      </button>
      <a className="btn btn--secondary btn--small" href={`/s/${id}`} target="_blank" rel="noreferrer">
        Open
      </a>
    </div>
  );
}

export function SurveyDetailPage({ id }: { id: string }) {
  const survey = useLoad(() => api.survey(id), [id]);
  const results = useLoad(() => api.surveyResults(id), [id]);
  const analyses = useLoad(() => api.analyses({ kind: "survey", limit: 200 }).then((all) => all.filter((a) => a.survey_id === id)), [id]);
  const campaigns = useCampaigns();
  const [draft, setDraft] = useState<Survey | null>(null);
  const [tab, setTab] = useState<"edit" | "results">("edit");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);

  useEffect(() => {
    if (survey.data) {
      setDraft(survey.data);
      if (survey.data.status !== "draft") setTab("results");
    }
  }, [survey.data]);

  if (!draft) {
    return (
      <Shell title="Survey">
        <ErrorAlert error={survey.error} />
        {!survey.error && <p className="muted">Loading survey…</p>}
      </Shell>
    );
  }

  const s = draft;
  const editable = s.status === "draft";
  const act = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  };
  const update = (patch: Partial<Survey>) => {
    setSaved(false);
    setDraft({ ...s, ...patch });
  };
  const setQuestion = (i: number, q: SurveyQuestion) => update({ questions: s.questions.map((x, j) => (j === i ? q : x)) });
  const move = (i: number, delta: number) => {
    const next = [...s.questions];
    [next[i], next[i + delta]] = [next[i + delta], next[i]];
    update({ questions: next });
  };
  const save = () =>
    act("save", async () => {
      const updated = await api.updateSurvey(s.id, {
        title: s.title,
        description: s.description,
        campaign_id: s.campaign_id,
        ...(editable ? { questions: s.questions } : {}),
      });
      setDraft(updated);
      setSaved(true);
    });
  const publish = () =>
    act("publish", async () => {
      if (editable) await save();
      const updated = await api.publishSurvey(s.id);
      setDraft(updated);
      survey.reload();
    });
  const close = () => act("close", async () => setDraft(await api.closeSurvey(s.id)));
  const remove = () =>
    window.confirm(`Delete “${s.title}” and all ${s.response_count} responses?`) &&
    act("delete", async () => {
      await api.deleteSurvey(s.id);
      navigate("/surveys");
    });
  const analyse = () =>
    act("analyse", async () => {
      const created = await api.analyzeSurvey(s.id);
      setAnalysis(created);
      analyses.reload();
    });

  return (
    <Shell title={s.title}>
      <PageHeader
        back={{ to: "/surveys", label: "All surveys" }}
        title={s.title}
        subtitle={
          <>
            <StatusBadge status={s.status} /> · {results.data?.total_responses ?? s.response_count} real responses
            {s.published_at && ` · published ${formatDate(s.published_at)}`}
          </>
        }
        actions={
          <>
            {s.status !== "published" && (
              <button className="btn" onClick={publish} disabled={!!busy}>
                <Send size={15} /> {s.status === "closed" ? "Reopen" : "Publish"}
              </button>
            )}
            {s.status === "published" && (
              <button className="btn btn--secondary" onClick={close} disabled={!!busy}>
                <Lock size={15} /> Close survey
              </button>
            )}
            <button className="btn btn--danger" onClick={remove} disabled={!!busy}>
              <Trash2 size={15} />
            </button>
          </>
        }
      />
      <div className="stack">
        <ErrorAlert error={error} />
        {s.status !== "draft" && (
          <Card title={s.status === "published" ? "Share this link with customers" : "Survey closed"} subtitle={s.status === "published" ? "Anyone with the link can answer; each submission is stored as a real response." : "The link shows the survey but no longer accepts responses."}>
            <ShareLink id={s.id} />
          </Card>
        )}
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === "edit"} className={`tab ${tab === "edit" ? "is-active" : ""}`} onClick={() => setTab("edit")}>
            {editable ? "Edit questions" : "Questions"}
          </button>
          <button role="tab" aria-selected={tab === "results"} className={`tab ${tab === "results" ? "is-active" : ""}`} onClick={() => setTab("results")}>
            Results & analysis
          </button>
        </div>

        {tab === "edit" && (
          <>
            {!editable && (
              <Notice>
                <p>Questions are locked after publishing so every response answers the same questions. You can still edit the title, description and campaign.</p>
              </Notice>
            )}
            <Card title="Survey details">
              <div className="form">
                <label className="field">
                  <span>Title</span>
                  <input className="input" value={s.title} onChange={(e) => update({ title: e.target.value })} maxLength={255} />
                </label>
                <label className="field">
                  <span>Description shown to respondents</span>
                  <textarea className="textarea" value={s.description} onChange={(e) => update({ description: e.target.value })} maxLength={2000} />
                </label>
                <CampaignSelect value={s.campaign_id ?? ""} onChange={(v) => update({ campaign_id: v || null })} campaigns={campaigns.data} />
              </div>
            </Card>
            {s.questions.map((q, i) =>
              editable ? (
                <QuestionEditor key={i} q={q} index={i} total={s.questions.length} onChange={(nq) => setQuestion(i, nq)} onMove={(d) => move(i, d)} onRemove={() => update({ questions: s.questions.filter((_, j) => j !== i) })} />
              ) : (
                <div key={q.id} className="q-card">
                  <div className="q-card__head">
                    <span className="q-card__num">Q{i + 1}</span>
                    <span className="badge">{TYPE_LABEL[q.type]}</span>
                  </div>
                  <div>{q.text}</div>
                  {q.options.length > 0 && <div className="muted small">{q.options.join(" · ")}</div>}
                  {q.type === "rating" && <div className="muted small">{q.scale_min} ({q.scale_min_label}) – {q.scale_max} ({q.scale_max_label})</div>}
                </div>
              ),
            )}
            <div className="page-header__actions">
              {editable && s.questions.length < 30 && (
                <>
                  <button className="btn btn--secondary btn--small" onClick={() => update({ questions: [...s.questions, newQuestion("multiple_choice")] })}>
                    <Plus size={13} /> Multiple choice
                  </button>
                  <button className="btn btn--secondary btn--small" onClick={() => update({ questions: [...s.questions, newQuestion("rating")] })}>
                    <Plus size={13} /> Rating
                  </button>
                  <button className="btn btn--secondary btn--small" onClick={() => update({ questions: [...s.questions, newQuestion("open_ended")] })}>
                    <Plus size={13} /> Open-ended
                  </button>
                </>
              )}
              <span style={{ flex: 1 }} />
              {saved && <span className="small" style={{ color: "var(--ok)" }}>Saved.</span>}
              <button className="btn" onClick={save} disabled={!!busy}>
                {busy === "save" ? "Saving…" : "Save changes"}
              </button>
            </div>
          </>
        )}

        {tab === "results" && (
          <>
            <Card
              title="Responses"
              subtitle="Counts and percentages are computed from real submissions only. No sample or synthetic data is ever added."
              actions={
                <div className="page-header__actions">
                  <a className="btn btn--secondary btn--small" href={responsesCsvUrl(s.id)} download>
                    <Download size={14} /> Export CSV
                  </a>
                  <button className="btn btn--small" onClick={analyse} disabled={!!busy || !results.data?.total_responses}>
                    <Sparkles size={14} /> {busy === "analyse" ? "Analysing…" : "Analyse with AI"}
                  </button>
                </div>
              }
            >
              <p className="prose" style={{ margin: 0 }}>
                <strong>{results.data?.total_responses ?? 0}</strong> real responses collected.
                {s.status === "draft" && " Publish the survey to start collecting responses."}
                {!!results.data?.total_responses && results.data.total_responses <= 10 && " Small sample: treat percentages as indicative."}
              </p>
              {(analyses.data?.length ?? 0) > 0 && (
                <p className="small" style={{ marginBottom: 0 }}>
                  Previous AI analyses:{" "}
                  {analyses.data!.map((a, i) => (
                    <span key={a.id}>
                      {i > 0 && " · "}
                      <Link to={`/insights/${a.id}`}>{formatDate(a.created_at, true)}</Link>
                    </span>
                  ))}
                </p>
              )}
            </Card>
            {busy === "analyse" && (
              <Card>
                <Working title="Survey Agent is analysing the responses…" steps={["Computing results", "Finding patterns", "Analysing open-ended answers", "Writing insights"]} />
              </Card>
            )}
            {analysis && busy !== "analyse" && <AnalysisView analysis={analysis} onDeleted={() => { setAnalysis(null); analyses.reload(); }} />}
            {!analysis && results.data && results.data.total_responses > 0 && <SurveyResultsBody stats={results.data} />}
          </>
        )}
      </div>
    </Shell>
  );
}

// ---------- Public survey (respondents) ----------

export function PublicSurveyPage({ id }: { id: string }) {
  const status = useAiStatus();
  const survey = useLoad(() => api.publicSurvey(id), [id]);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [state, setState] = useState<"answering" | "sending" | "done">("answering");
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    if (survey.data) document.title = survey.data.title;
  }, [survey.data]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setState("sending");
    setError(null);
    try {
      await api.submitSurveyResponse(id, answers);
      setState("done");
    } catch (err) {
      setError(err);
      setState("answering");
    }
  };
  const s = survey.data;

  return (
    <div className="public">
      <div className="public__inner">
        <div className="public__brand">
          <LogoMark size={30} /> {status?.company ?? ""}
        </div>
        {survey.error && <ErrorAlert error={survey.error} />}
        {s && state === "done" && (
          <div className="card">
            <h1>Thank you!</h1>
            <p className="prose">Your response has been recorded. We really appreciate your time.</p>
          </div>
        )}
        {s && state !== "done" && (
          <form className="card form" onSubmit={submit}>
            <div>
              <h1>{s.title}</h1>
              {s.description && <p className="prose">{s.description}</p>}
            </div>
            {!s.accepting_responses && (
              <Notice tone="warn">
                <p>This survey is closed and no longer accepts responses.</p>
              </Notice>
            )}
            {s.questions.map((q, i) => (
              <fieldset key={q.id} className="public__question" disabled={!s.accepting_responses}>
                <legend>
                  {i + 1}. {q.text} {q.required && <span className="required" aria-label="required">*</span>}
                </legend>
                {q.type === "multiple_choice" &&
                  q.options.map((option) => {
                    const current = answers[q.id];
                    const checked = q.allow_multiple ? Array.isArray(current) && current.includes(option) : current === option;
                    return (
                      <label key={option} className="choice">
                        <input
                          type={q.allow_multiple ? "checkbox" : "radio"}
                          name={q.id}
                          checked={checked}
                          onChange={(e) =>
                            setAnswers((a) => {
                              if (!q.allow_multiple) return { ...a, [q.id]: option };
                              const list = Array.isArray(a[q.id]) ? (a[q.id] as string[]) : [];
                              return { ...a, [q.id]: e.target.checked ? [...list, option] : list.filter((o) => o !== option) };
                            })
                          }
                        />
                        {option}
                      </label>
                    );
                  })}
                {q.type === "multiple_choice" && q.allow_multiple && <small className="muted">Select all that apply.</small>}
                {q.type === "rating" && q.scale_min != null && q.scale_max != null && (
                  <>
                    <div className="rating" role="radiogroup" aria-label={q.text}>
                      {Array.from({ length: q.scale_max - q.scale_min + 1 }, (_, k) => q.scale_min! + k).map((v) => (
                        <button key={v} type="button" role="radio" aria-checked={answers[q.id] === v} className={`rating__btn ${answers[q.id] === v ? "is-selected" : ""}`} onClick={() => setAnswers((a) => ({ ...a, [q.id]: v }))}>
                          {v}
                        </button>
                      ))}
                    </div>
                    <div className="scale-ends">
                      <span>{q.scale_min_label}</span>
                      <span>{q.scale_max_label}</span>
                    </div>
                  </>
                )}
                {q.type === "open_ended" && (
                  <textarea className="textarea" value={(answers[q.id] as string) ?? ""} onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))} maxLength={2000} aria-label={q.text} />
                )}
              </fieldset>
            ))}
            <ErrorAlert error={error} />
            {s.accepting_responses && (
              <button className="btn" disabled={state === "sending"}>
                {state === "sending" ? "Sending…" : "Submit"}
              </button>
            )}
          </form>
        )}
        {!s && !survey.error && <p className="muted">Loading…</p>}
      </div>
    </div>
  );
}
