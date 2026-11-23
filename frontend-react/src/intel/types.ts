// Types for campaigns and the AI marketing modules (mirrors backend/models/intelligence.py).

export type CampaignStatus = "draft" | "planned" | "active" | "completed";
export type AnalysisKind = "competitor" | "research" | "sentiment" | "survey" | "strategy";

export interface EvidenceItem {
  id: string;
  kind: "document" | "web" | "user" | "analysis";
  title: string;
  text: string;
  url: string | null;
  document: string | null;
  page: number | null;
  section: string | null;
  retrieved_at: string;
  published: string | null;
}

/** A claim with the evidence ids that support it; unverified = AI inference. */
export interface Point {
  text: string;
  sources: string[];
  verified?: boolean;
}

export interface Recommendation {
  action: string;
  rationale: string;
  priority: "high" | "medium" | "low";
  sources?: string[];
  verified?: boolean;
  topics?: string[];
}

export interface CampaignFields {
  name: string;
  product: string;
  objective: string;
  target_audience: string;
  positioning: string;
  key_message: string;
  budget: number | null;
  start_date: string | null;
  end_date: string | null;
  channels: string[];
  kpis: string[];
  status: CampaignStatus;
  notes: string;
}

export interface Campaign extends CampaignFields {
  id: string;
  origin: "user" | "documents";
  origin_sources: EvidenceItem[];
  created_at: string;
  updated_at: string;
}

export interface CampaignProposal extends Omit<CampaignFields, "status" | "positioning"> {
  origin_sources: EvidenceItem[];
}

export interface AnalysisSummary {
  id: string;
  kind: AnalysisKind;
  title: string;
  campaign_id: string | null;
  campaign_name: string | null;
  survey_id: string | null;
  live_research: boolean;
  summary: string;
  created_at: string;
}

export interface Analysis<R = any> extends AnalysisSummary {
  input: Record<string, any>;
  result: R;
  evidence: EvidenceItem[];
  model: string;
}

export interface SurveySummary {
  id: string;
  title: string;
  status: "draft" | "published" | "closed";
  campaign_id: string | null;
  response_count: number;
  created_at: string;
  published_at: string | null;
}

export type QuestionType = "multiple_choice" | "rating" | "open_ended";

export interface SurveyQuestion {
  id: string;
  type: QuestionType;
  text: string;
  options: string[];
  allow_multiple: boolean;
  scale_min: number | null;
  scale_max: number | null;
  scale_min_label: string;
  scale_max_label: string;
  required: boolean;
}

export interface Survey extends SurveySummary {
  description: string;
  product: string;
  objective: string;
  audience: string;
  questions: SurveyQuestion[];
}

export interface CampaignDetail extends Campaign {
  analyses: AnalysisSummary[];
  surveys: SurveySummary[];
}

export interface AiStatus {
  ai_configured: boolean;
  model: string | null;
  web_search: { provider: string | null; configured: boolean };
  company: string;
}

export interface SentimentStats {
  total: number;
  counts: Record<"positive" | "neutral" | "negative", number>;
  percentages: Record<"positive" | "neutral" | "negative", number>;
  net_score: number;
  topics: { topic: string; mentions: number; positive: number; neutral: number; negative: number }[];
}

export interface SentimentResult {
  stats: SentimentStats;
  summary: {
    overall_summary: string;
    satisfaction_level: string;
    complaints: { issue: string; topics: string[]; example: string }[];
    expectations: string[];
    strengths: { text: string; topics: string[] }[];
    weaknesses: { text: string; topics: string[] }[];
    recommendations: Recommendation[];
  };
  items: { index: number; text: string; sentiment: "positive" | "neutral" | "negative"; confidence: number; topics: string[] }[];
}

export interface SurveyResults {
  total_responses: number;
  questions: {
    id: string;
    type: QuestionType;
    text: string;
    answered: number;
    options?: { option: string; count: number; percent: number }[];
    distribution?: { value: number; count: number }[];
    average?: number | null;
    scale_min?: number;
    scale_max?: number;
    scale_min_label?: string;
    scale_max_label?: string;
    answers?: string[];
  }[];
}

export interface AgentStep {
  type: "step";
  id: number;
  agent: string;
  action: string;
  status: "running" | "done" | "error";
  detail: string;
  analysis_id?: string;
  kind?: AnalysisKind;
  survey_id?: string;
}

export type AgentEvent = AgentStep | { type: "answer"; text: string } | { type: "error"; message: string };
