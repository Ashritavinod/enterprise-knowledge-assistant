import { useState, type CSSProperties } from "react";
import { AlertTriangle, Check, ChevronDown, Copy, FileText, RotateCcw, SearchX } from "lucide-react";
import type { Message, Source } from "../types";
import { documentColor, documentTitle } from "../topics";
import { LogoMark } from "./Logo";
import { RichText } from "./RichText";

function SourceCard({ source, index }: { source: Source; index: number }) {
  const [open, setOpen] = useState(false);
  const color = documentColor(source.document);
  const match = Math.round(Math.max(0, Math.min(1, source.score)) * 100);

  return (
    <div className={`source ${open ? "is-open" : ""}`} style={{ "--doc": color } as CSSProperties}>
      <button className="source__head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="source__index">{index + 1}</span>
        <span className="source__icon">
          <FileText size={15} />
        </span>
        <span className="source__meta">
          <span className="source__title">{documentTitle(source.document)}</span>
          <span className="source__page">
            {source.section ? `${source.section} · ` : ""}Page {source.page}
          </span>
        </span>
        <span className="source__match" title={`Similarity score ${source.score.toFixed(3)}`}>
          <span className="meter">
            <span className="meter__fill" style={{ width: `${match}%` }} />
          </span>
          {match}%
        </span>
        <ChevronDown className="source__chevron" size={16} />
      </button>
      {open && (
        <div className="source__body">
          <RichText text={source.excerpt} />
        </div>
      )}
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard blocked – ignore */
    }
  };
  return (
    <button className="action-btn" onClick={copy}>
      {copied ? <Check size={14} /> : <Copy size={14} />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

interface Props {
  message: Message;
  onRetry?: (question: string) => void;
}

export function ChatMessage({ message, onRetry }: Props) {
  if (message.role === "user") {
    return (
      <div className="msg msg--user">
        <div className="bubble bubble--user">{message.text}</div>
      </div>
    );
  }

  const sources = message.sources ?? [];
  const top = sources[0];

  return (
    <div className="msg msg--assistant">
      <div className="avatar">
        <LogoMark size={32} />
      </div>
      <div className="bubble bubble--assistant">
        {message.status === "error" ? (
          <div className="notice notice--error">
            <AlertTriangle size={18} />
            <div>
              <strong>Couldn't reach the knowledge base.</strong>
              <p>{message.text}</p>
            </div>
          </div>
        ) : !message.found ? (
          <div className="notice notice--empty">
            <SearchX size={18} />
            <p>{message.text}</p>
          </div>
        ) : (
          <>
            {top && (
              <div className="answer-label" style={{ "--doc": documentColor(top.document) } as CSSProperties}>
                From <strong>{documentTitle(top.document)}</strong>
                {top.section && <> · {top.section}</>} · p. {top.page}
              </div>
            )}
            <RichText text={message.text} />
          </>
        )}

        {sources.length > 0 && (
          <div className="sources">
            <div className="sources__heading">
              Sources <span className="pill">{sources.length}</span>
            </div>
            {sources.map((s, i) => (
              <SourceCard key={`${s.document}-${s.page}-${i}`} source={s} index={i} />
            ))}
          </div>
        )}

        <div className="msg__actions">
          {message.status === "done" && message.found && <CopyButton text={message.text} />}
          {message.status === "error" && message.question && onRetry && (
            <button className="action-btn" onClick={() => onRetry(message.question!)}>
              <RotateCcw size={14} />
              Retry
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function TypingIndicator() {
  return (
    <div className="msg msg--assistant" aria-label="MarketMind is searching">
      <div className="avatar">
        <LogoMark size={32} />
      </div>
      <div className="bubble bubble--assistant bubble--typing">
        <span className="typing">
          <span />
          <span />
          <span />
        </span>
        Searching marketing documents…
      </div>
    </div>
  );
}
