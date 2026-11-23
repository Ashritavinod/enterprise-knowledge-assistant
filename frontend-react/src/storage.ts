// Chat history is stored in PostgreSQL by the backend; these helpers map the
// API's conversation shapes onto the UI's types.
import { request } from "./api";
import type { Conversation, Message, Source } from "./types";

interface ApiMessage {
  id: number;
  role: "user" | "assistant";
  text: string;
  found: boolean | null;
  sources: Source[] | null;
  created_at: string;
}

interface ApiConversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages?: ApiMessage[];
}

function toConversation(api: ApiConversation): Conversation {
  let lastQuestion: string | undefined;
  const messages: Message[] = (api.messages ?? []).map((m) => {
    const createdAt = Date.parse(m.created_at);
    if (m.role === "user") {
      lastQuestion = m.text;
      return { id: String(m.id), role: "user", text: m.text, createdAt };
    }
    return {
      id: String(m.id),
      role: "assistant",
      status: "done",
      createdAt,
      text: m.text,
      found: m.found ?? undefined,
      sources: m.sources ?? [],
      question: lastQuestion,
    };
  });
  return {
    id: api.id,
    title: api.title,
    updatedAt: Date.parse(api.updated_at),
    messages,
    loaded: api.messages !== undefined,
  };
}

export const loadConversations = () =>
  request<ApiConversation[]>("/conversations").then((list) => list.map(toConversation));

export const loadConversation = (id: string) =>
  request<ApiConversation>(`/conversations/${id}`).then(toConversation);

export const createConversation = (title: string) =>
  request<ApiConversation>("/conversations", {
    method: "POST",
    body: JSON.stringify({ title }),
  }).then(toConversation);

export const deleteConversation = (id: string) =>
  request<void>(`/conversations/${id}`, { method: "DELETE" });
