import { useCallback, useEffect, useRef, useState } from "react";
import { Menu, Plus } from "lucide-react";
import { askQuestion, checkHealth, fetchDocuments } from "./api";
import { ChatMessage, TypingIndicator } from "./components/ChatMessage";
import { Composer } from "./components/Composer";
import { EmptyState } from "./components/EmptyState";
import { Sidebar, type BackendStatus } from "./components/Sidebar";
import { createConversation, deleteConversation, loadConversation, loadConversations } from "./storage";
import type { Conversation, DocumentInfo, Message } from "./types";

/** Id prefix for a chat not yet saved to the backend. */
const LOCAL_PREFIX = "local-";
const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
const titleFrom = (q: string) => (q.length > 48 ? `${q.slice(0, 45).trimEnd()}…` : q);

export default function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [status, setStatus] = useState<BackendStatus>("checking");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const active = conversations.find((c) => c.id === activeId) ?? null;
  const historyLoaded = useRef(false);

  // Poll backend health; once reachable, load documents and (once) chat history.
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      const ok = await checkHealth().catch(() => false);
      if (cancelled) return;
      setStatus(ok ? "online" : "offline");
      if (!ok) return;
      fetchDocuments().then((d) => !cancelled && setDocuments(d)).catch(() => {});
      if (!historyLoaded.current) {
        loadConversations()
          .then((saved) => {
            if (cancelled) return;
            historyLoaded.current = true;
            setConversations((current) => {
              // Keep chats started before history arrived; they're newest.
              const ids = new Set(current.map((c) => c.id));
              return [...current, ...saved.filter((c) => !ids.has(c.id))];
            });
          })
          .catch(() => {});
      }
    };
    poll();
    const timer = setInterval(poll, 15000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  // Keep the newest message in view.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [active?.messages.length, busy]);

  const appendMessage = (conversationId: string, message: Message) =>
    setConversations((all) =>
      all
        .map((c) =>
          c.id === conversationId
            ? { ...c, messages: [...c.messages, message], updatedAt: Date.now() }
            : c,
        )
        .sort((a, b) => b.updatedAt - a.updatedAt),
    );

  const send = useCallback(
    async (question: string) => {
      if (busy) return;
      let conversationId = activeId;
      if (!conversationId) {
        // Shown immediately; swapped for the server's conversation once created.
        conversationId = `${LOCAL_PREFIX}${uid()}`;
        const fresh: Conversation = {
          id: conversationId,
          title: titleFrom(question),
          updatedAt: Date.now(),
          messages: [],
          loaded: true,
        };
        setConversations((all) => [fresh, ...all]);
        setActiveId(conversationId);
      }
      setSidebarOpen(false);
      appendMessage(conversationId, { id: uid(), role: "user", text: question, createdAt: Date.now() });

      const controller = new AbortController();
      abortRef.current = controller;
      setBusy(true);
      try {
        if (conversationId.startsWith(LOCAL_PREFIX)) {
          const localId = conversationId;
          const created = await createConversation(titleFrom(question));
          conversationId = created.id;
          setConversations((all) =>
            all.map((c) => (c.id === localId ? { ...c, id: created.id } : c)),
          );
          setActiveId((current) => (current === localId ? created.id : current));
        }
        const result = await askQuestion(question, conversationId, controller.signal);
        setStatus("online");
        appendMessage(conversationId, {
          id: uid(),
          role: "assistant",
          status: "done",
          createdAt: Date.now(),
          text: result.answer,
          found: result.found,
          sources: result.sources,
          question,
        });
      } catch (error) {
        if (controller.signal.aborted) return;
        setStatus("offline");
        appendMessage(conversationId, {
          id: uid(),
          role: "assistant",
          status: "error",
          createdAt: Date.now(),
          text:
            error instanceof Error && /\(4\d\d\)/.test(error.message)
              ? `${error.message}. Please rephrase and try again.`
              : "The backend didn't respond. Make sure the FastAPI server is running on port 8000, then retry.",
          question,
        });
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
        setBusy(false);
      }
    },
    [activeId, busy],
  );

  const stop = () => abortRef.current?.abort();

  const newChat = () => {
    stop();
    setActiveId(null);
    setSidebarOpen(false);
  };

  const remove = (id: string) => {
    setConversations((all) => all.filter((c) => c.id !== id));
    if (id === activeId) setActiveId(null);
    if (!id.startsWith(LOCAL_PREFIX)) {
      deleteConversation(id).catch(() => {
        /* already gone or backend offline; it reappears on the next reload if it survived */
      });
    }
  };

  const select = (id: string) => {
    stop();
    setActiveId(id);
    setSidebarOpen(false);
    const target = conversations.find((c) => c.id === id);
    if (target && !target.loaded) {
      loadConversation(id)
        .then((full) =>
          setConversations((all) =>
            // Keep any messages added locally while the fetch was in flight.
            all.map((c) => (c.id === id && !c.loaded ? { ...full, messages: [...full.messages, ...c.messages] } : c)),
          ),
        )
        .catch(() => setStatus("offline"));
    }
  };

  return (
    <div className="app">
      <Sidebar
        open={sidebarOpen}
        conversations={conversations}
        activeId={activeId}
        documents={documents}
        status={status}
        onNewChat={newChat}
        onSelect={select}
        onDelete={remove}
        onClose={() => setSidebarOpen(false)}
      />
      {sidebarOpen && <div className="scrim" onClick={() => setSidebarOpen(false)} />}

      <main className="main">
        <header className="topbar">
          <button className="icon-btn topbar__menu" onClick={() => setSidebarOpen(true)} aria-label="Open menu">
            <Menu size={20} />
          </button>
          <div className="topbar__title">{active ? active.title : "New conversation"}</div>
          {active && (
            <button className="ghost-btn" onClick={newChat}>
              <Plus size={16} />
              <span>New</span>
            </button>
          )}
        </header>

        <div className="scroll" ref={scrollRef}>
          {!active || active.messages.length === 0 ? (
            <EmptyState onPick={send} />
          ) : (
            <div className="thread" aria-live="polite">
              {active.messages.map((m) => (
                <ChatMessage key={m.id} message={m} onRetry={send} />
              ))}
              {busy && <TypingIndicator />}
            </div>
          )}
        </div>

        <Composer busy={busy} onSend={send} onStop={stop} />
      </main>
    </div>
  );
}
