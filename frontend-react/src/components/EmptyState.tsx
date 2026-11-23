import type { CSSProperties } from "react";
import { ArrowUpRight, Sparkles } from "lucide-react";
import { TOPICS } from "../topics";

export function EmptyState({ onPick }: { onPick: (prompt: string) => void }) {
  return (
    <div className="empty">
      <div className="empty__badge">
        <Sparkles size={14} />
        Grounded in Honeycrumb's marketing playbooks
      </div>
      <h1 className="empty__title">
        What are we <span className="gradient-text">baking up</span> today?
      </h1>
      <p className="empty__subtitle">
        Your sous-chef for Honeycrumb marketing. Ask about brand standards, campaign approvals,
        the 2026 plan, menu launches and the Crumb Club. Every answer links back to its source.
      </p>

      <div className="topic-grid">
        {TOPICS.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              className="topic-card"
              style={{ "--topic": t.color, "--topic-soft": t.soft } as CSSProperties}
              onClick={() => onPick(t.prompt)}
            >
              <span className="topic-card__head">
                <span className="topic-card__icon">
                  <Icon size={18} />
                </span>
                <span className="topic-card__label">{t.label}</span>
                <ArrowUpRight className="topic-card__arrow" size={16} />
              </span>
              <span className="topic-card__prompt">{t.prompt}</span>
              <span className="topic-card__blurb">{t.blurb}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
