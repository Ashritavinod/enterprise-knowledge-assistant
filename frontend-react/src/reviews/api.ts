// API client for the customer reviews dataset and the Review Insights Agent.
import type { Insight, Overview, ProductsResponse, Review, ReviewFilters } from "./types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "/api";

export async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, { ...init, headers: { "Content-Type": "application/json" } });
  } catch {
    throw new Error("The backend didn't respond. Make sure the API is running on port 8000.");
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const detail = (await response.json()).detail;
      if (typeof detail === "string") message = detail;
    } catch {
      /* not JSON */
    }
    const error = new Error(message) as Error & { status?: number };
    error.status = response.status;
    throw error;
  }
  return (await response.json()) as T;
}

export const filterQuery = (filters: ReviewFilters) =>
  new URLSearchParams(
    Object.entries(filters)
      .filter(([, v]) => v !== undefined && v !== "")
      .map(([k, v]) => [k, String(v)]),
  ).toString();

export const exportUrl = (filters: ReviewFilters) => `${BASE}/reviews/export.csv?${filterQuery(filters)}`;

export const reviewsApi = {
  overview: () => call<Overview>("/reviews/overview"),
  products: () => call<ProductsResponse>("/reviews/products"),
  reviews: (filters: ReviewFilters, limit: number, offset: number) =>
    call<{ total: number; items: Review[] }>(`/reviews?${filterQuery(filters)}&limit=${limit}&offset=${offset}`),
  latestInsight: () =>
    call<Insight>("/reviews/insights/latest").catch((e: Error & { status?: number }) => {
      if (e.status === 404) return null;
      throw e;
    }),
  runInsights: (reclassify = false) =>
    call<Insight>("/reviews/insights", { method: "POST", body: JSON.stringify({ reclassify }) }),
};
