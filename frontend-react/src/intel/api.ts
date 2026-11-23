// API client for campaigns and the AI marketing modules.
import type {
  AgentEvent,
  AiStatus,
  Analysis,
  AnalysisKind,
  AnalysisSummary,
  Campaign,
  CampaignDetail,
  CampaignFields,
  CampaignProposal,
  Survey,
  SurveyResults,
  SurveySummary,
} from "./types";

export const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "/api";

/** An API error carrying the backend's `detail` message for display. */
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc, msg}]
    return detail
      .map((d: any) => `${(d.loc ?? []).filter((l: unknown) => l !== "body").join(" → ")}: ${d.msg}`)
      .join("; ");
  }
  return "";
}

export async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "The backend didn't respond. Make sure the API is running on port 8000.");
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = describe(body.detail) || message;
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const post = <T>(path: string, body?: unknown) =>
  call<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const reportUrl = (id: string, format: "md" | "pdf") => `${API_BASE}/analyses/${id}/report.${format}`;
export const responsesCsvUrl = (id: string) => `${API_BASE}/surveys/${id}/responses.csv`;
export const publicSurveyUrl = (id: string) => `${window.location.origin}/s/${id}`;

export const api = {
  status: () => call<AiStatus>("/ai/status"),

  campaigns: () => call<Campaign[]>("/campaigns"),
  campaign: (id: string) => call<CampaignDetail>(`/campaigns/${id}`),
  createCampaign: (body: Partial<CampaignFields> & { name: string; origin?: string; origin_sources?: unknown[] }) =>
    post<Campaign>("/campaigns", body),
  updateCampaign: (id: string, body: Partial<CampaignFields>) =>
    call<Campaign>(`/campaigns/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteCampaign: (id: string) => call<void>(`/campaigns/${id}`, { method: "DELETE" }),
  importProposals: () => post<{ campaigns: CampaignProposal[] }>("/campaigns/import-proposals"),
  applyStrategy: (campaignId: string, analysisId: string) =>
    post<{ campaign: Campaign; applied_fields: string[] }>(`/campaigns/${campaignId}/apply-strategy/${analysisId}`),

  analyses: (params: { kind?: AnalysisKind; campaign_id?: string; limit?: number } = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== "") as [string, string][],
    );
    return call<AnalysisSummary[]>(`/analyses?${query}`);
  },
  analysis: <R = any>(id: string) => call<Analysis<R>>(`/analyses/${id}`),
  deleteAnalysis: (id: string) => call<void>(`/analyses/${id}`, { method: "DELETE" }),

  competitors: (body: unknown) => post<Analysis>("/competitors/analyze", body),
  research: (body: unknown) => post<Analysis>("/research/analyze", body),
  sentiment: (body: unknown) => post<Analysis>("/sentiment/analyze", body),
  strategy: (body: unknown) => post<Analysis>("/strategy/generate", body),

  surveys: (campaignId?: string) =>
    call<SurveySummary[]>(`/surveys${campaignId ? `?campaign_id=${campaignId}` : ""}`),
  survey: (id: string) => call<Survey>(`/surveys/${id}`),
  generateSurvey: (body: unknown) => post<Survey>("/surveys/generate", body),
  updateSurvey: (id: string, body: unknown) =>
    call<Survey>(`/surveys/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  publishSurvey: (id: string) => post<Survey>(`/surveys/${id}/publish`),
  closeSurvey: (id: string) => post<Survey>(`/surveys/${id}/close`),
  deleteSurvey: (id: string) => call<void>(`/surveys/${id}`, { method: "DELETE" }),
  surveyResults: (id: string) => call<SurveyResults>(`/surveys/${id}/results`),
  analyzeSurvey: (id: string) => post<Analysis>(`/surveys/${id}/analyze`),

  publicSurvey: (id: string) =>
    call<{ id: string; title: string; description: string; questions: Survey["questions"]; accepting_responses: boolean }>(
      `/public/surveys/${id}`,
    ),
  submitSurveyResponse: (id: string, answers: Record<string, unknown>) =>
    post<{ id: number; message: string }>(`/public/surveys/${id}/responses`, { answers }),
};

/** Stream the AI team (supervisor) reply; calls onEvent for each step/answer/error. */
export async function agentChat(
  body: { message: string; campaign_id?: string | null; history: { role: string; content: string }[] },
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/agent/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError(0, "The backend didn't respond. Make sure the API is running on port 8000.");
  }
  if (!response.ok || !response.body) {
    let message = `Request failed (${response.status})`;
    try {
      message = describe((await response.json()).detail) || message;
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, message);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffered = "";
  const handle = (line: string) => line.trim() && onEvent(JSON.parse(line) as AgentEvent);
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffered += decoder.decode(value, { stream: true });
    const lines = buffered.split("\n");
    buffered = lines.pop() ?? "";
    lines.forEach(handle);
  }
  handle(buffered + decoder.decode());
}
