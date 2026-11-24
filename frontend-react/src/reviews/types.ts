// Types for the customer reviews dataset (mirrors backend/routes/reviews.py).

export type Sentiment = "positive" | "neutral" | "negative";

export interface Overview {
  products: number;
  reviews: number;
  analysed: number;
  first_review: string | null;
  last_review: string | null;
  latest_insight_at: string | null;
  ai_configured: boolean;
  model: string | null;
}

export interface ProductStats {
  id: number;
  sku: string;
  name: string;
  category: string;
  price: number;
  availability: string;
  reviews: number;
  analysed: number;
  avg_rating: number | null;
  sentiment: Record<Sentiment, number>;
  sentiment_pct: Record<Sentiment, number | null>;
  net_sentiment: number | null;
  top_topics: { topic: string; mentions: number; negative: number }[];
  units_12m: number;
  revenue_12m: number;
  units_prev_12m: number;
  growth_pct: number | null;
  holiday_share_pct: number;
  december_share_pct: number;
  monthly_units: number[];
  seasonal: boolean;
  season: string;
  peak_months: string[];
  active_months: number;
  top3_share_pct: number;
}

export interface Rankings {
  best_reviewed: number[];
  needs_attention: number[];
  most_units: number[];
  most_revenue: number[];
  fastest_growing: number[];
  seasonal: number[];
  christmas_sellers: number[];
}

export interface ProductsResponse {
  months: string[];
  products: ProductStats[];
  rankings: Rankings;
}

export interface Review {
  id: number;
  product_id: number;
  product: string;
  customer: string;
  rating: number;
  text: string;
  channel: string;
  city: string;
  review_date: string;
  sentiment: Sentiment | null;
  confidence: number | null;
  topics: string[];
}

export interface ReviewFilters {
  product_id?: number;
  sentiment?: Sentiment | "unanalysed";
  rating?: number;
  q?: string;
  sort?: "newest" | "oldest" | "rating_high" | "rating_low";
}

export interface Quote {
  id: number;
  product: string;
  sentiment: Sentiment;
  rating: number;
  date: string;
  text: string;
}

export interface Report {
  summary: string;
  best_reviewed: { product: string; why: string; review_ids: number[] }[];
  in_demand: { product: string; why: string }[];
  seasonal: { product: string; season: string; why: string }[];
  needs_attention: { product: string; issue: string; fix: string; review_ids: number[] }[];
  christmas: {
    headline: string;
    hero_products: { product: string; why: string; message: string; ideas: string[]; review_ids: number[] }[];
    bundles: string[];
    timing: string;
    avoid: { product: string; why: string }[];
  };
  recommendations: { action: string; rationale: string; priority: "high" | "medium" | "low" }[];
  quotes: Record<string, Quote>;
}

export interface Insight {
  id: number;
  model: string;
  created_at: string;
  stats: ProductsResponse & { totals: { products: number; reviews: number; analysed: number } };
  report: Report;
  classified?: { classified: number; skipped: number };
}
