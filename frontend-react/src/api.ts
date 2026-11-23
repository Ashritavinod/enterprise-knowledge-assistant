import type { AskResponse, DocumentInfo } from "./types";

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

export const fetchDocuments = () =>
  request<{ documents: DocumentInfo[] }>("/qa/documents").then((r) => r.documents);

// /health answers 503 when PostgreSQL is down, which counts as offline.
export const checkHealth = () =>
  request<{ status: string }>("/health").then((r) => r.status === "ok");
