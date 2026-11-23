import type { AskResponse, DocumentInfo, StreamEvent } from "./types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "/api";

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const askQuestion = (question: string, conversationId: string, signal?: AbortSignal) =>
  request<AskResponse>("/qa/ask", {
    method: "POST",
    body: JSON.stringify({ question, conversation_id: conversationId }),
    signal,
  });

/**
 * Ask with a streamed reply: calls `onEvent` for each newline-delimited JSON
 * event as it arrives (sources, then text deltas, then done). Resolves with
 * the final "done" event.
 */
export async function askQuestionStream(
  question: string,
  conversationId: string,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<Extract<StreamEvent, { type: "done" }>> {
  const response = await fetch(`${BASE}/qa/ask/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, conversation_id: conversationId }),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`Request failed (${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffered = "";
  let done: Extract<StreamEvent, { type: "done" }> | undefined;
  const handle = (line: string) => {
    if (!line.trim()) return;
    const event = JSON.parse(line) as StreamEvent;
    if (event.type === "done") done = event;
    onEvent(event);
  };
  for (;;) {
    const { value, done: finished } = await reader.read();
    if (finished) break;
    buffered += decoder.decode(value, { stream: true });
    const lines = buffered.split("\n");
    buffered = lines.pop() ?? "";
    lines.forEach(handle);
  }
  handle(buffered + decoder.decode());
  if (!done) throw new Error("The reply ended early");
  return done;
}

export const fetchDocuments = () =>
  request<{ documents: DocumentInfo[] }>("/qa/documents").then((r) => r.documents);

// /health answers 503 when PostgreSQL is down, which counts as offline.
export const checkHealth = () =>
  request<{ status: string }>("/health").then((r) => r.status === "ok");
