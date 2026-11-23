export interface Source {
  document: string;
  page: number;
  section?: string;
  excerpt: string;
  score: number;
}

export interface AskResponse {
  question: string;
  answer: string;
  found: boolean;
  sources: Source[];
  conversation_id?: string | null;
}

export interface DocumentInfo {
  name: string;
  title: string;
}

export type Message =
  | { id: string; role: "user"; text: string; createdAt: number }
  | {
      id: string;
      role: "assistant";
      createdAt: number;
      status: "done" | "error";
      text: string;
      found?: boolean;
      sources?: Source[];
      question?: string;
    };

export interface Conversation {
  id: string;
  title: string;
  updatedAt: number;
  messages: Message[];
  /** False until the conversation's messages have been fetched from the API. */
  loaded: boolean;
}
