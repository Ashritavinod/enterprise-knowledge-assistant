// Customer Reviews: the PostgreSQL reviews dataset and the Review Insights Agent.
import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, ChevronLeft, ChevronRight, Download, Info, Menu, RefreshCw, Search, Sparkles, X } from "lucide-react";
import { checkHealth, fetchDocuments } from "../api";
import { Sidebar, type BackendStatus } from "../components/Sidebar";
import type { DocumentInfo } from "../types";
import { exportUrl, reviewsApi } from "./api";
import { MonthlyBars, SentimentBadge, SentimentBar, SentimentLegend, Stars, formatNumber, monthLabel } from "./charts";
import { InsightsReport } from "./InsightsReport";
import type { Insight, Overview, ProductsResponse, Review, ReviewFilters } from "./types";

const PAGE_SIZE = 25;
const NEW_REVIEW_POLL_MS = 20000; // how often the page checks for newly arrived reviews

export function useBackend() {
  const [status, setStatus] = useState<BackendStatus>("checking");
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      const ok = await checkHealth().catch(() => false);
      if (cancelled) return;
      setStatus(ok ? "online" : "offline");
      if (ok) fetchDocuments().then((d) => !cancelled && setDocuments(d)).catch(() => {});
    };
    poll();
    const timer = setInterval(poll, 20000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);
  return { status, documents };
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div className="alert alert--error" role="alert">
      <AlertTriangle size={16} /> {error instanceof Error ? error.message : String(error)}
    </div>
  );
}

const STEPS = ["Reading new reviews", "Classifying sentiment", "Calculating demand and seasonality", "Writing the marketing report"];

function Working() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  const current = Math.min(STEPS.length - 1, Math.floor(seconds / 8));
  return (
    <div className="working" role="status" aria-live="polite">
      <div className="spinner" />
      <div>
        <strong>The Review Insights Agent is working…</strong>
        <div className="small muted">{seconds}s · the first run classifies every review and takes about a minute</div>
        <ol className="steps">
          {STEPS.map((step, i) => (
            <li key={step} className={i < current ? "is-done" : i === current ? "is-current" : ""}>
              {i < current ? "✓" : i === current ? "…" : "○"} {step}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

// ---------- AI insights ----------

function InsightsCard({ overview, onDone }: { overview: Overview | null; onDone: () => void }) {
  const [insight, setInsight] = useState<Insight | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    reviewsApi
      .latestInsight()
      .then(setInsight)
      .catch(setError)
      .finally(() => setLoading(false));
  }, []);

  const run = async () => {
    setRunning(true);
    setError(null);
    try {
      setInsight(await reviewsApi.runInsights());
      onDone();
    } catch (e) {
      setError(e);
    } finally {
      setRunning(false);
    }
  };

  const pending = overview ? overview.reviews - overview.analysed : 0;
  return (
    <section className="card">
      <div className="card__head">
        <div>
          <h2 className="card__title">
            <Sparkles size={18} /> AI insights
          </h2>
          <p className="card__subtitle">
            {insight
              ? `Last run ${new Date(insight.created_at).toLocaleString()}`
              : "The agent reads every review, labels its sentiment, and tells you what customers love, what sells, what's seasonal and what to market at Christmas."}
          </p>
        </div>
        <div className="run-row">
          {insight && pending > 0 && !running && (
            <span className="new-badge" role="status" title="Not analysed yet. Run again to include them in the report.">
              <span className="new-badge__dot" aria-hidden="true" />
              {pending} new {pending === 1 ? "review" : "reviews"}
            </span>
          )}
          <button className="btn" onClick={run} disabled={running || overview?.ai_configured === false}>
            {insight ? <RefreshCw size={15} /> : <Sparkles size={15} />} {running ? "Analysing…" : insight ? "Run again" : "Run AI analysis"}
          </button>
        </div>
      </div>
      {overview?.ai_configured === false && (
        <div className="alert alert--warn">
          <Info size={16} /> Azure OpenAI is not configured, so the AI analysis can't run. You can still browse the dataset below.
        </div>
      )}
      <ErrorNote error={error} />
      {running ? <Working /> : loading ? <p className="muted small">Loading…</p> : insight && <InsightsReport insight={insight} />}
    </section>
  );
}

// ---------- Products ----------

function ProductsTable({ data, onPick }: { data: ProductsResponse; onPick: (id: number) => void }) {
  return (
    <section className="card">
      <div className="card__head">
        <div>
          <h2 className="card__title">Products</h2>
          <p className="card__subtitle">
            Ratings and sentiment from customer reviews; units sold in the last 12 months. Darker bars are November and
            December. Click a product to read its reviews.
          </p>
        </div>
        <SentimentLegend />
      </div>
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th>Product</th>
              <th>Season</th>
              <th className="num">Reviews</th>
              <th>Rating</th>
              <th>Sentiment</th>
              <th className="num">Units (12 mo)</th>
              <th>Monthly sales</th>
            </tr>
          </thead>
          <tbody>
            {data.products.map((p) => (
              <tr key={p.id} className="is-clickable" onClick={() => onPick(p.id)}>
                <td>
                  <div className="cell-title">{p.name}</div>
                  <div className="small muted">
                    {p.category} · ${p.price.toFixed(2)}
                  </div>
                </td>
                <td>
                  <span className={`chip ${p.seasonal ? "chip--season" : ""}`}>{p.season}</span>
                </td>
                <td className="num">{p.reviews}</td>
                <td>
                  {p.avg_rating != null && (
                    <span className="nowrap">
                      <Stars value={p.avg_rating} /> {p.avg_rating.toFixed(1)}
                    </span>
                  )}
                </td>
                <td style={{ minWidth: 170 }}>
                  <SentimentBar pct={p.sentiment_pct} counts={p.sentiment} />
                </td>
                <td className="num">
                  {formatNumber(p.units_12m)}
                  <div className={`small ${p.growth_pct != null && p.growth_pct < 0 ? "down" : "muted"}`}>
                    {p.growth_pct == null ? "new" : `${p.growth_pct > 0 ? "+" : ""}${p.growth_pct}%`}
                  </div>
                </td>
                <td style={{ minWidth: 170 }}>
                  <MonthlyBars months={data.months} units={p.monthly_units} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ---------- Reviews ----------

function ReviewsTable({
  data,
  filters,
  setFilters,
  refreshKey,
}: {
  data: ProductsResponse | null;
  filters: ReviewFilters;
  setFilters: (f: ReviewFilters) => void;
  refreshKey: number;
}) {
  const [page, setPage] = useState(0);
  const [result, setResult] = useState<{ total: number; items: Review[] } | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [search, setSearch] = useState(filters.q ?? "");

  useEffect(() => setPage(0), [filters]);
  useEffect(() => setSearch(filters.q ?? ""), [filters.q]);
  useEffect(() => {
    let cancelled = false;
    reviewsApi
      .reviews(filters, PAGE_SIZE, page * PAGE_SIZE)
      .then((r) => !cancelled && (setResult(r), setError(null)))
      .catch((e) => !cancelled && setError(e));
    return () => {
      cancelled = true;
    };
  }, [filters, page, refreshKey]);

  // Search as you type, slightly delayed.
  useEffect(() => {
    const timer = setTimeout(() => (search !== (filters.q ?? "") ? setFilters({ ...filters, q: search }) : undefined), 300);
    return () => clearTimeout(timer);
  }, [search]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (patch: Partial<ReviewFilters>) => setFilters({ ...filters, ...patch });
  const total = result?.total ?? 0;
  const active = Object.values(filters).some((v) => v !== undefined && v !== "" && v !== "newest");

  return (
    <section className="card" id="reviews">
      <div className="card__head">
        <div>
          <h2 className="card__title">Reviews</h2>
          <p className="card__subtitle">Every review in the dataset, with the sentiment and topics the AI assigned.</p>
        </div>
        <a className="btn btn--secondary" href={exportUrl(filters)} download>
          <Download size={15} /> Export CSV
        </a>
      </div>
      <div className="filters">
        <label className="search">
          <Search size={15} />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search reviews, customers, cities…" aria-label="Search reviews" />
        </label>
        <select
          value={filters.product_id ?? ""}
          onChange={(e) => set({ product_id: e.target.value ? Number(e.target.value) : undefined })}
          aria-label="Product"
        >
          <option value="">All products</option>
          {data?.products.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <select
          value={filters.sentiment ?? ""}
          onChange={(e) => set({ sentiment: (e.target.value || undefined) as ReviewFilters["sentiment"] })}
          aria-label="Sentiment"
        >
          <option value="">Any sentiment</option>
          <option value="positive">Positive</option>
          <option value="neutral">Neutral</option>
          <option value="negative">Negative</option>
          <option value="unanalysed">Not analysed</option>
        </select>
        <select value={filters.rating ?? ""} onChange={(e) => set({ rating: e.target.value ? Number(e.target.value) : undefined })} aria-label="Rating">
          <option value="">Any rating</option>
          {[5, 4, 3, 2, 1].map((r) => (
            <option key={r} value={r}>
              {r} star{r > 1 ? "s" : ""}
            </option>
          ))}
        </select>
        <select value={filters.sort ?? "newest"} onChange={(e) => set({ sort: e.target.value as ReviewFilters["sort"] })} aria-label="Sort">
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
          <option value="rating_high">Highest rated</option>
          <option value="rating_low">Lowest rated</option>
        </select>
        {active && (
          <button
            className="btn btn--ghost"
            onClick={() => {
              setSearch("");
              setFilters({});
            }}
          >
            <X size={14} /> Clear
          </button>
        )}
      </div>
      <ErrorNote error={error} />
      <div className="table-scroll">
        <table className="table table--reviews">
          <thead>
            <tr>
              <th>Date</th>
              <th>Product</th>
              <th>Rating</th>
              <th>Review</th>
              <th>Sentiment</th>
            </tr>
          </thead>
          <tbody>
            {result?.items.map((r) => (
              <tr key={r.id}>
                <td className="nowrap small">{r.review_date}</td>
                <td className="small">{r.product}</td>
                <td>
                  <Stars value={r.rating} />
                </td>
                <td>
                  <div>{r.text}</div>
                  <div className="small muted">
                    {r.customer} · {r.city} · {r.channel} · #{r.id}
                  </div>
                  {r.topics.length > 0 && (
                    <div className="topics">
                      {r.topics.map((t) => (
                        <span key={t} className="chip chip--topic">
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </td>
                <td>
                  <SentimentBadge sentiment={r.sentiment} />
                </td>
              </tr>
            ))}
            {result && result.items.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  No reviews match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="pager">
        <span className="small muted">
          {total ? `${page * PAGE_SIZE + 1}–${Math.min(total, (page + 1) * PAGE_SIZE)} of ${formatNumber(total)}` : "0 reviews"}
        </span>
        <button className="icon-btn" disabled={page === 0} onClick={() => setPage(page - 1)} aria-label="Previous page">
          <ChevronLeft size={18} />
        </button>
        <button className="icon-btn" disabled={(page + 1) * PAGE_SIZE >= total} onClick={() => setPage(page + 1)} aria-label="Next page">
          <ChevronRight size={18} />
        </button>
      </div>
    </section>
  );
}

// ---------- Page ----------

export function ReviewsPage() {
  const [open, setOpen] = useState(false);
  const { status, documents } = useBackend();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [products, setProducts] = useState<ProductsResponse | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [filters, setFilters] = useState<ReviewFilters>({});
  const [refreshKey, setRefreshKey] = useState(0);
  const reviewsRef = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    Promise.all([reviewsApi.overview(), reviewsApi.products()])
      .then(([o, p]) => {
        setOverview(o);
        setProducts(p);
        setError(null);
      })
      .catch(setError);
  }, []);
  useEffect(() => {
    document.title = "Customer Reviews · MarketMind";
    load();
  }, [load]);

  // New reviews can arrive while the page is open (the live review feed), so check
  // the totals now and then and refresh the tables when the count changes.
  const knownTotal = useRef<number | null>(null);
  useEffect(() => {
    knownTotal.current = overview?.reviews ?? null;
  }, [overview]);
  useEffect(() => {
    const timer = setInterval(() => {
      reviewsApi
        .overview()
        .then((o) => {
          if (knownTotal.current !== null && o.reviews !== knownTotal.current) {
            reviewsApi.products().then(setProducts).catch(() => undefined);
            setRefreshKey((k) => k + 1);
          }
          setOverview(o);
        })
        .catch(() => undefined); // a missed poll is harmless; the next one retries
    }, NEW_REVIEW_POLL_MS);
    return () => clearInterval(timer);
  }, []);

  const pickProduct = (id: number) => {
    setFilters({ product_id: id });
    reviewsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="app">
      <Sidebar open={open} documents={documents} status={status} onClose={() => setOpen(false)} />
      {open && <div className="scrim" onClick={() => setOpen(false)} />}
      <main className="main">
        <header className="topbar">
          <button className="icon-btn topbar__menu" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu size={20} />
          </button>
          <div className="topbar__title">Customer Reviews</div>
        </header>
        <div className="scroll">
          <div className="page">
            <div className="page-header">
              <h1>Customer reviews</h1>
              <p>
                {overview
                  ? `${overview.products} products · ${formatNumber(overview.reviews)} reviews · ${monthLabel(overview.first_review ?? "")} to ${monthLabel(overview.last_review ?? "")} · ${formatNumber(overview.analysed)} analysed by AI`
                  : "Loading the dataset…"}
              </p>
              <p className="small muted">
                <Info size={12} /> Sample dataset generated for this demo. Products, prices and seasons come from the
                company documents; reviews and sales figures are illustrative.
              </p>
            </div>
            <ErrorNote error={error} />
            <InsightsCard
              overview={overview}
              onDone={() => {
                load();
                setRefreshKey((k) => k + 1);
              }}
            />
            {products && <ProductsTable data={products} onPick={pickProduct} />}
            <div ref={reviewsRef} style={{ scrollMarginTop: 12 }}>
              <ReviewsTable data={products} filters={filters} setFilters={setFilters} refreshKey={refreshKey} />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
