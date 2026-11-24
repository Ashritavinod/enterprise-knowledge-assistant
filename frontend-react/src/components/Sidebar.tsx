import { FileText, MessageSquare, MessagesSquare, Plus, Star, Trash2, X, type LucideIcon } from "lucide-react";
import type { Conversation, DocumentInfo } from "../types";
import { documentColor } from "../topics";
import { Link, usePath } from "../router";
import { Logo } from "./Logo";

export type BackendStatus = "checking" | "online" | "offline";

interface ChatProps {
  conversations: Conversation[];
  activeId: string | null;
  onNewChat: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

interface Props {
  open: boolean;
  documents: DocumentInfo[];
  status: BackendStatus;
  onClose: () => void;
  /** Chat history; shown on the Assistant page only. */
  chat?: ChatProps;
}

const STATUS_LABEL: Record<BackendStatus, string> = {
  checking: "Connecting…",
  online: "Knowledge base online",
  offline: "Backend offline",
};

const NAV: { to: string; label: string; icon: LucideIcon }[] = [
  { to: "/", label: "Assistant", icon: MessagesSquare },
  { to: "/reviews", label: "Customer Reviews", icon: Star },
];

export function Sidebar({ open, documents, status, onClose, chat }: Props) {
  const path = usePath();
  return (
    <aside className={`sidebar ${open ? "is-open" : ""}`} aria-label="Navigation">
      <div className="sidebar__top">
        <Logo />
        <button className="icon-btn sidebar__close" onClick={onClose} aria-label="Close menu">
          <X size={18} />
        </button>
      </div>

      <nav className="nav" aria-label="Pages">
        {NAV.map(({ to, label, icon: Icon }) => {
          const active = to === "/" ? path === "/" : path.startsWith(to);
          return (
            <Link
              key={to}
              to={to}
              className={`nav__item ${active ? "is-active" : ""}`}
              aria-current={active ? "page" : undefined}
              onClick={onClose}
            >
              <Icon size={16} />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>

      {chat && (
        <>
          <button className="new-chat" onClick={chat.onNewChat}>
            <Plus size={18} strokeWidth={2.5} />
            New conversation
          </button>

          <nav className="sidebar__section sidebar__section--grow" aria-label="Recent conversations">
            <h2 className="sidebar__heading">Recent</h2>
            {chat.conversations.length === 0 ? (
              <p className="sidebar__empty">Your conversations will appear here.</p>
            ) : (
              <ul className="history">
                {chat.conversations.map((c) => (
                  <li key={c.id}>
                    <div className={`history__item ${c.id === chat.activeId ? "is-active" : ""}`}>
                      <button className="history__select" onClick={() => chat.onSelect(c.id)} title={c.title}>
                        <MessageSquare size={15} />
                        <span>{c.title}</span>
                      </button>
                      <button
                        className="history__delete"
                        onClick={() => chat.onDelete(c.id)}
                        aria-label={`Delete conversation “${c.title}”`}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </nav>
        </>
      )}

      <section className={`sidebar__section ${chat ? "" : "sidebar__section--push"}`}>
        <h2 className="sidebar__heading">Knowledge base</h2>
        <ul className="doc-list">
          {documents.map((d) => (
            <li key={d.name} title={d.name}>
              <span className="doc-list__icon" style={{ color: documentColor(d.name) }}>
                <FileText size={15} />
              </span>
              {d.title}
            </li>
          ))}
          {documents.length === 0 && <li className="sidebar__empty">No documents loaded.</li>}
        </ul>
      </section>

      <footer className={`status status--${status}`} role="status">
        <span className="status__dot" />
        {STATUS_LABEL[status]}
      </footer>
    </aside>
  );
}
