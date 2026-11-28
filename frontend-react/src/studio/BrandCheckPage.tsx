// Brand Check: paste draft copy and get every guideline it breaks, with citations and a fix.
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, CircleCheck, Info, RefreshCw, ShieldCheck, Sparkles, WandSparkles } from "lucide-react";
import { ErrorNote } from "../reviews/ReviewsPage";
import { studioApi, takeDraft, type BrandCheck, type BrandIssue, type CheckChannel, type Severity } from "./api";
import { Citations, CopyButton, PageShell, Segmented, Thinking } from "./shared";

const CHANNELS: { value: CheckChannel; label: string }[] = [
  { value: "social", label: "Social post" },
  { value: "email", label: "Email" },
  { value: "website", label: "Web banner" },
  { value: "menu", label: "Menu / packaging" },
  { value: "other", label: "Other" },
];

const EXAMPLE = {
  channel: "social" as CheckChannel,
  text:
    "HURRY!! Last chance 😍🎉🔥🥐 Our skinny Lemon Honey Chiffon is the most guilt-free treat in town. " +
    "Life is sweeter by every crumb. #cake #bakery #portland #yum",
};

const SEVERITY: Record<Severity, { label: string; className: string }> = {
  must_fix: { label: "Must fix", className: "sev--must" },
  should_fix: { label: "Should fix", className: "sev--should" },
  suggestion: { label: "Suggestion", className: "sev--tip" },
};

const VERDICT: Record<BrandCheck["verdict"], { label: string; className: string }> = {
  on_brand: { label: "On brand", className: "verdict--good" },
  minor_changes: { label: "Minor changes needed", className: "verdict--warn" },
  needs_changes: { label: "Needs changes", className: "verdict--bad" },
  not_reviewable: { label: "Nothing to review", className: "verdict--warn" },
};

/** The draft with every quoted problem highlighted. */
function HighlightedDraft({ text, issues }: { text: string; issues: BrandIssue[] }) {
  const parts = useMemo(() => {
    const quotes = [...new Set(issues.map((i) => i.quote).filter((q) => q.length > 1))];
    const ranges: [number, number, Severity][] = [];
    const lower = text.toLowerCase();
    for (const q of quotes) {
      const severity = issues.find((i) => i.quote === q)!.severity;
      // Emoji and hashtag findings list several items separated by spaces; mark each.
      const pieces = text.includes(q) || lower.includes(q.toLowerCase()) ? [q] : q.split(" ");
      for (const piece of pieces) {
        let from = 0;
        let at: number;
        while (piece && (at = lower.indexOf(piece.toLowerCase(), from)) !== -1) {
          ranges.push([at, at + piece.length, severity]);
          from = at + piece.length;
        }
      }
    }
    ranges.sort((a, b) => a[0] - b[0]);
    const out: ReactNode[] = [];
    let pos = 0;
    for (const [start, end, severity] of ranges) {
      if (start < pos) continue; // overlapping: keep the first
      out.push(text.slice(pos, start));
      out.push(
        <mark key={start} className={`hl ${SEVERITY[severity].className}`}>
          {text.slice(start, end)}
        </mark>,
      );
      pos = end;
    }
    out.push(text.slice(pos));
    return out;
  }, [text, issues]);
  return <div className="draft-view">{parts}</div>;
}

function IssueCard({ issue, passages }: { issue: BrandIssue; passages: BrandCheck["passages"] }) {
  const sev = SEVERITY[issue.severity];
  return (
    <li className={`issue ${sev.className}`}>
      <div className="issue__head">
        <span className={`sev ${sev.className}`}>{sev.label}</span>
        <strong>{issue.category}</strong>
        <span className="issue__by small muted">{issue.source === "rule" ? "Brand rule" : "AI review"}</span>
      </div>
      {issue.quote && <div className="issue__quote">“{issue.quote}”</div>}
      <p className="issue__problem">{issue.problem}</p>
      <p className="issue__fix">
        <WandSparkles size={14} /> <span>{issue.fix}</span>
      </p>
      <Citations numbers={issue.citations} passages={passages} />
    </li>
  );
}

export function BrandCheckPage() {
  const [channel, setChannel] = useState<CheckChannel>("social");
  const [subject, setSubject] = useState("");
  const [text, setText] = useState("");
  const [result, setResult] = useState<BrandCheck | null>(null);
  const [checked, setChecked] = useState<{ text: string; subject: string } | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    document.title = "Brand Check · MarketMind";
    const draft = takeDraft();
    if (draft) {
      setChannel(draft.channel);
      setText(draft.text);
      setSubject(draft.subject ?? "");
      run(draft.text, draft.channel, draft.subject ?? "");
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function run(draft = text, ch = channel, subj = subject) {
    if (!draft.trim()) return;
    setRunning(true);
    setError(null);
    try {
      setResult(await studioApi.check(draft, ch, ch === "email" ? subj : ""));
      setChecked({ text: draft, subject: ch === "email" ? subj : "" });
    } catch (e) {
      setError(e);
    } finally {
      setRunning(false);
    }
  }

  const useRevised = () => {
    if (!result) return;
    let revised = result.revised;
    let subj = "";
    const m = /^\s*subject\s*:\s*(.+)\n+/i.exec(revised);
    if (m && channel === "email") {
      subj = m[1].trim();
      revised = revised.slice(m[0].length);
    }
    setText(revised);
    setSubject(subj);
    run(revised, channel, subj);
  };

  const counts = result
    ? (["must_fix", "should_fix", "suggestion"] as Severity[]).map((s) => [s, result.issues.filter((i) => i.severity === s).length] as const)
    : [];

  return (
    <PageShell title="Brand Check">
      <div className="page-header">
        <h1>Brand check</h1>
        <p>
          Paste draft copy and check it against the Honeycrumb brand guidelines. Hard rules (banned words, emoji and
          hashtag limits, subject length, palette, tagline) are checked automatically; the AI reviews tone and style.
          Every issue links to the guideline it comes from.
        </p>
      </div>

      <section className="card">
        <div className="field">
          <span className="field__label">Channel</span>
          <Segmented value={channel} options={CHANNELS} onChange={setChannel} label="Channel" />
        </div>
        {channel === "email" && (
          <label className="field">
            <span className="field__label">
              Subject line <span className="muted small">{subject.length}/45</span>
            </span>
            <input className="input" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Our holiday cookie tins are back" />
          </label>
        )}
        <label className="field">
          <span className="field__label">Draft copy</span>
          <textarea
            className="input textarea"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={7}
            maxLength={4000}
            placeholder="Paste a caption, email, banner or menu description…"
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) run();
            }}
          />
        </label>
        <div className="run-row run-row--start">
          <button className="btn" onClick={() => run()} disabled={running || !text.trim()}>
            <ShieldCheck size={15} /> {running ? "Checking…" : "Check copy"}
          </button>
          <button
            className="btn btn--ghost"
            onClick={() => {
              setChannel(EXAMPLE.channel);
              setText(EXAMPLE.text);
            }}
            disabled={running}
          >
            Try an example
          </button>
          <span className="small muted">Ctrl+Enter to check</span>
        </div>
      </section>

      <ErrorNote error={error} />
      {running && <Thinking text="Checking against the brand guidelines…" />}

      {result && checked && !running && result.score === null && (
        <div className="alert alert--warn">
          <Info size={16} /> {result.summary}
        </div>
      )}

      {result && checked && !running && result.score !== null && (
        <>
          <section className="card">
            <div className="verdict-row">
              <div className={`score ${VERDICT[result.verdict].className}`} aria-label={`Brand score ${result.score} out of 100`}>
                <span className="score__num">{result.score}</span>
                <span className="score__of">/100</span>
              </div>
              <div className="verdict-row__text">
                <div className={`verdict ${VERDICT[result.verdict].className}`}>
                  {result.verdict === "on_brand" ? <CircleCheck size={16} /> : <AlertTriangle size={16} />} {VERDICT[result.verdict].label}
                </div>
                <p className="verdict-row__summary">{result.summary}</p>
                <div className="sev-counts">
                  {counts.map(([s, n]) => (
                    <span key={s} className={`sev ${SEVERITY[s].className} ${n ? "" : "is-zero"}`}>
                      {n} {SEVERITY[s].label.toLowerCase()}
                    </span>
                  ))}
                </div>
              </div>
            </div>
            {!result.model && (
              <div className="alert alert--warn">
                <Info size={16} />
                {result.ai_error
                  ? `The AI review failed (${result.ai_error}); only the automated brand rules were checked.`
                  : "Azure OpenAI is not configured, so only the automated brand rules were checked."}
              </div>
            )}
            {result.model && result.ai_error && (
              <div className="alert alert--warn">
                <Info size={16} /> The suggested rewrite couldn't be written ({result.ai_error}). The review below is complete.
              </div>
            )}
            {result.model && !result.ai_error && !result.revised && result.issues.length > 0 && (
              <p className="small muted">
                No suggested rewrite: the AI's rewrites didn't score better than your draft on a full re-check. Use the fixes
                below.
              </p>
            )}
            {result.issues.length > 0 && (
              <div>
                <h3 className="sub-title">Your draft</h3>
                {checked.subject && (
                  <div className="draft-view draft-view--subject">
                    <span className="muted small">Subject: </span>
                    <HighlightedDraft text={checked.subject} issues={result.issues} />
                  </div>
                )}
                <HighlightedDraft text={checked.text} issues={result.issues} />
              </div>
            )}
          </section>

          {result.issues.length > 0 ? (
            <section className="card">
              <h2 className="card__title">What to fix</h2>
              <ul className="issues">
                {result.issues.map((issue, i) => (
                  <IssueCard key={i} issue={issue} passages={result.passages} />
                ))}
              </ul>
            </section>
          ) : (
            <div className="alert alert--ok">
              <CircleCheck size={16} /> No issues found. This copy follows the brand guidelines.
            </div>
          )}

          {(result.strengths.length > 0 || result.revised) && (
            <div className="studio-grid">
              {result.strengths.length > 0 && (
                <section className="card">
                  <h2 className="card__title">
                    <CircleCheck size={18} /> What works
                  </h2>
                  <ul className="plain-list">
                    {result.strengths.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ul>
                </section>
              )}
              {result.revised && (
                <section className="card">
                  <div className="card__head">
                    <h2 className="card__title">
                      <Sparkles size={18} /> Suggested rewrite
                    </h2>
                    <div className="run-row">
                      <CopyButton text={result.revised} />
                      <button className="btn btn--secondary btn--sm" onClick={useRevised}>
                        <RefreshCw size={14} /> Use and re-check
                      </button>
                    </div>
                  </div>
                  <div className="draft-view">{result.revised}</div>
                  {result.revised_flags.length > 0 ? (
                    <div className="alert alert--warn">
                      <AlertTriangle size={16} /> Re-checked: scores {result.revised_score}/100 (yours: {result.score}). Still
                      flagged: {[...new Set(result.revised_flags.map((f) => f.category))].join(", ")}.
                    </div>
                  ) : (
                    <p className="small ok-text">
                      <CircleCheck size={13} /> Re-checked: scores {result.revised_score}/100 with no issues (brand rules and AI
                      review).
                    </p>
                  )}
                </section>
              )}
            </div>
          )}
        </>
      )}
    </PageShell>
  );
}
