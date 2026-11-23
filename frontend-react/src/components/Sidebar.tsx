import { FileText, MessageSquare, Plus, Trash2, X } from "lucide-react";
import type { Conversation, DocumentInfo } from "../types";
import { documentColor } from "../topics";
import { Logo } from "./Logo";

export type BackendStatus = "checking" | "online" | "offline";

interface Props {
  open: boolean;
  conversations: Conversation[];
  activeId: string | null;
  documents: DocumentInfo[];
  status: BackendStatus;
  onNewChat: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}

const STATUS_LABEL: Record<BackendStatus, string> = {
  checking: "Connecting…",
  online: "Recipe book online",
  offline: "Backend offline",
};

export function Sidebar({
  open,
  conversations,
  activeId,
  documents,
  status,
  onNewChat,
  onSelect,
  onDelete,
  onClose,
}: Props) {
  return (
    <aside className={`sidebar ${open ? "is-open" : ""}`} aria-label="Navigation">
      <div className="sidebar__top">
        <Logo />
        <button className="icon-btn sidebar__close" onClick={onClose} aria-label="Close menu">
          <X size={18} />
        </button>
      </div>

      <button className="new-chat" onClick={onNewChat}>
        <Plus size={18} strokeWidth={2.5} />
        New conversation
      </button>

      <nav className="sidebar__section sidebar__section--grow">
        <h2 className="sidebar__heading">Recent</h2>
        {conversations.length === 0 ? (
          <p className="sidebar__empty">Your conversations will appear here.</p>
        ) : (
          <ul className="history">
            {conversations.map((c) => (
              <li key={c.id}>
                <div className={`history__item ${c.id === activeId ? "is-active" : ""}`}>
                  <button className="history__select" onClick={() => onSelect(c.id)} title={c.title}>
                    <MessageSquare size={15} />
                    <span>{c.title}</span>
                  </button>
                  <button
                    className="history__delete"
                    onClick={() => onDelete(c.id)}
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

      <section className="sidebar__section">
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
