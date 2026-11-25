// API client for the Brand Compliance Checker and the Campaign Copywriter.
import { call } from "../reviews/api";
import type { Source } from "../types";

export type Severity = "must_fix" | "should_fix" | "suggestion";
export type CheckChannel = "social" | "email" | "website" | "menu" | "other";
export type CopyChannel = "instagram" | "email" | "menu_board";

export interface BrandIssue {
  severity: Severity;
  category: string;
  /** The words of the draft the issue is about; "" when something is missing. */
  quote: string;
  problem: string;
  fix: string;
  /** 1-based numbers into `passages`. */
  citations: number[];
  source: "rule" | "ai";
}

export interface BrandCheck {
  channel: CheckChannel;
  verdict: "on_brand" | "minor_changes" | "needs_changes";
  score: number;
  summary: string;
  issues: BrandIssue[];
  strengths: string[];
  revised: string;
  revised_flags: BrandIssue[];
  passages: Source[];
  model: string | null;
  ai_error: string | null;
}

export interface VerifiedQuote {
  review_id: number;
  excerpt: string;
  customer: string;
  city: string;
  rating: number;
  date: string;
}

export interface CopyVariant {
  angle: string;
  headline: string;
  preheader: string;
  body: string;
  cta: string;
  hashtags: string[];
  quotes: VerifiedQuote[];
  citations: number[];
  brand_flags: BrandIssue[];
}

export interface CopyResult {
  product: { id: number; name: string; category: string; price: number; availability: string };
  channel: CopyChannel;
  variants: CopyVariant[];
  availability_note: string | null;
  reviews_offered: number;
  passages: Source[];
  model: string;
}

export const studioApi = {
  check: (text: string, channel: CheckChannel, subject = "") =>
    call<BrandCheck>("/brand/check", { method: "POST", body: JSON.stringify({ text, channel, subject }) }),
  generate: (product_id: number, channel: CopyChannel, notes = "") =>
    call<CopyResult>("/copy/generate", { method: "POST", body: JSON.stringify({ product_id, channel, notes }) }),
};

/** Hand a draft from the Copywriter to the Brand Check page (session only). */
const HANDOFF = "marketmind:brand-check-draft";
export function handOffDraft(draft: { text: string; channel: CheckChannel; subject?: string }) {
  try {
    sessionStorage.setItem(HANDOFF, JSON.stringify(draft));
  } catch {
    /* storage unavailable: the page just opens empty */
  }
}
export function takeDraft(): { text: string; channel: CheckChannel; subject?: string } | null {
  try {
    const raw = sessionStorage.getItem(HANDOFF);
    sessionStorage.removeItem(HANDOFF);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
