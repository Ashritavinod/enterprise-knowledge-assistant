import { useCallback, useEffect, useRef, useState } from "react";
import { Menu, Plus } from "lucide-react";
import { askQuestionStream, checkHealth, fetchDocuments } from "./api";
import { ChatMessage } from "./components/ChatMessage";
import { Composer } from "./components/Composer";
import { EmptyState } from "./components/EmptyState";
import { Sidebar, type BackendStatus } from "./components/Sidebar";
import { createConversation, deleteConversation, loadConversation, loadConversations } from "./storage";
import type { Conversation, DocumentInfo, Message } from "./types";

type AssistantMessage = Extract<Message, { role: "assistant" }>;

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

  // Keep the newest message in view, including while a reply streams in.
  const lastText = active?.messages[active.messages.length - 1]?.text.length ?? 0;
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [active?.messages.length, busy]);
  useEffect(() => {
    // Instant (not smooth) while streaming, so many small updates don't fight each other.
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [lastText]);

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

  /** Update (or, by returning null, remove) an assistant message, whichever chat holds it. */
  const updateReply = (
    messageId: string,
    change: (m: AssistantMessage) => AssistantMessage | null,
  ) =>
    setConversations((all) =>
      all.map((c) =>
        c.messages.some((m) => m.id === messageId)
          ? {
              ...c,
              messages: c.messages.flatMap((m) => {
                if (m.id !== messageId || m.role !== "assistant") return [m];
                const next = change(m);
                return next ? [next] : [];
              }),
            }
          : c,
      ),
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

      // The reply bubble appears at once (as a typing indicator) and fills in
      // as the answer streams.
      const replyId = uid();
      appendMessage(conversationId, {
        id: replyId,
        role: "assistant",
        status: "streaming",
        createdAt: Date.now(),
        text: "",
        sources: [],
        question,
      });

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
        const result = await askQuestionStream(
          question,
          conversationId,
          (event) => {
            if (event.type === "sources") {
              updateReply(replyId, (m) => ({ ...m, sources: event.sources }));
            } else if (event.type === "delta") {
              updateReply(replyId, (m) => ({ ...m, text: m.text + event.text }));
            }
          },
          controller.signal,
        );
        setStatus("online");
        updateReply(replyId, (m) => ({ ...m, status: "done", text: result.answer, found: result.found }));
      } catch (error) {
        if (controller.signal.aborted) {
          // Stopped: keep what was written so far, or drop an empty bubble.
          updateReply(replyId, (m) => (m.text.trim() ? { ...m, status: "done", found: true } : null));
          return;
        }
        setStatus("offline");
        updateReply(replyId, (m) => ({
          ...m,
          status: "error",
          sources: [],
          text:
            error instanceof Error && /\(4\d\d\)/.test(error.message)
              ? `${error.message}. Please rephrase and try again.`
              : "The backend didn't respond. Make sure the FastAPI server is running on port 8000, then retry.",
        }));
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
            </div>
          )}
        </div>

        <Composer busy={busy} onSend={send} onStop={stop} />
      </main>
    </div>
  );
}
