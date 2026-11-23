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
  /** Azure OpenAI deployment that wrote the answer; null when it is the top passage. */
  model?: string | null;
}

/** One line of the /qa/ask/stream response. */
export type StreamEvent =
  | { type: "sources"; sources: Source[] }
  | { type: "delta"; text: string }
  | {
      type: "done";
      answer: string;
      found: boolean;
      model: string | null;
      conversation_id: string | null;
    };

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
      /** "streaming" while the reply is still being written. */
      status: "streaming" | "done" | "error";
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
