// Page shell, citations and small pieces shared by the Brand Check and Copywriter pages.
import { useState, type ReactNode } from "react";
import { Check, Copy, Menu } from "lucide-react";
import { Sidebar } from "../components/Sidebar";
import { useBackend } from "../reviews/ReviewsPage";
import { documentColor } from "../topics";
import type { Source } from "../types";

export function PageShell({ title, children }: { title: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const { status, documents } = useBackend();
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

/** Numbered citation chips; clicking one shows that guideline passage underneath. */
export function Citations({ numbers, passages }: { numbers: number[]; passages: Source[] }) {
  const [shown, setShown] = useState<number | null>(null);
  if (!numbers.length) return null;
  const passage = shown ? passages[shown - 1] : null;
  return (
    <div className="cites">
      <div className="cites__row">
        <span className="small muted">Source</span>
        {numbers.map((n) => {
          const p = passages[n - 1];
          if (!p) return null;
          return (
            <button
              key={n}
              className={`cite ${shown === n ? "is-open" : ""}`}
              onClick={() => setShown(shown === n ? null : n)}
              aria-expanded={shown === n}
              title={`${p.document}, page ${p.page}${p.section ? ` · ${p.section}` : ""}`}
            >
              <span className="cite__dot" style={{ background: documentColor(p.document) }} aria-hidden="true" />[{n}]{" "}
              {p.section ? p.section.split(">").pop()!.trim() : `${p.document} p.${p.page}`}
            </button>
          );
        })}
      </div>
      {passage && (
        <blockquote className="passage">
          <div className="small muted">
            {passage.document} · page {passage.page}
            {passage.section ? ` · ${passage.section}` : ""}
          </div>
          <div className="passage__text">{passage.excerpt}</div>
        </blockquote>
      )}
    </div>
  );
}

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setDone(true);
      setTimeout(() => setDone(false), 1500);
    } catch {
      /* clipboard blocked; nothing to do */
    }
  };
  return (
    <button className="btn btn--secondary btn--sm" onClick={copy}>
      {done ? <Check size={14} /> : <Copy size={14} />} {done ? "Copied" : label}
    </button>
  );
}

/** A segmented choice (radio group styled as pills). */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: string; icon?: ReactNode }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.value}
          role="radio"
          aria-checked={value === o.value}
          className={`segmented__item ${value === o.value ? "is-active" : ""}`}
          onClick={() => onChange(o.value)}
        >
          {o.icon}
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Thinking({ text }: { text: string }) {
  return (
    <div className="working" role="status" aria-live="polite">
      <div className="spinner" />
      <div>
        <strong>{text}</strong>
        <div className="small muted">Usually takes 5–15 seconds.</div>
      </div>
    </div>
  );
}
