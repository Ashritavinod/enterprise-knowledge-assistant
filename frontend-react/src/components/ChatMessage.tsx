import { useState, type CSSProperties } from "react";
import { AlertTriangle, Check, ChevronDown, Copy, FileText, RotateCcw, SearchX } from "lucide-react";
import type { Message, Source } from "../types";
import { documentColor, documentTitle } from "../topics";
import { LogoMark } from "./Logo";
import { RichText } from "./RichText";
import { copyText } from "../studio/shared";

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

/** The passage numbers (1 to `count`) the text cites, like [2] or [1][3]. */
function citedNumbers(text: string, count: number): Set<number> {
  const cited = new Set<number>();
  for (const m of text.matchAll(/\[(\d+)\]/g)) {
    const n = Number(m[1]);
    if (n >= 1 && n <= count) cited.add(n);
  }
  return cited;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    if (await copyText(text)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
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

  const streaming = message.status === "streaming";
  if (streaming && !message.text) return <TypingIndicator />;

  // Sources appear once the reply is complete, so the text has the stage while it streams.
  const retrieved = streaming ? [] : message.sources ?? [];
  const top = retrieved[0];
  // Without Azure OpenAI the answer is the top passage itself: label where it came from.
  const isPassage = top !== undefined && message.text === top.excerpt;
  // List only what the answer used: the passages it cites (keeping their numbers so
  // [4] in the text still matches card 4), or the one passage shown as the answer.
  // A reply that cites nothing (a greeting, "not in the documents") lists none.
  const cited = citedNumbers(message.text, retrieved.length);
  const sources = isPassage
    ? [{ source: top, number: 1 }]
    : retrieved.map((source, i) => ({ source, number: i + 1 })).filter((s) => cited.has(s.number));

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
        ) : !streaming && !message.found ? (
          <div className="notice notice--empty">
            <SearchX size={18} />
            <p>{message.text}</p>
          </div>
        ) : (
          <>
            {isPassage && (
              <div className="answer-label" style={{ "--doc": documentColor(top.document) } as CSSProperties}>
                From <strong>{documentTitle(top.document)}</strong>
                {top.section && <> · {top.section}</>} · p. {top.page}
              </div>
            )}
            <div className={streaming ? "is-streaming" : undefined}>
              <RichText text={message.text} />
            </div>
          </>
        )}

        {sources.length > 0 && (
          <div className="sources">
            <div className="sources__heading">
              Sources <span className="pill">{sources.length}</span>
            </div>
            {sources.map(({ source, number }) => (
              <SourceCard key={number} source={source} index={number - 1} />
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
    <div className="msg msg--assistant" aria-label="MarketMind is thinking">
      <div className="avatar">
        <LogoMark size={32} />
      </div>
      <div className="bubble bubble--assistant bubble--typing">
        <span className="typing">
          <span />
          <span />
          <span />
        </span>
        Thinking…
      </div>
    </div>
  );
}
