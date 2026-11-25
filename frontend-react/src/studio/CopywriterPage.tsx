// Copywriter: on-brand campaign copy for a product, built on verified customer quotes.
import { useEffect, useState, type ReactNode } from "react";
import { AlertTriangle, BadgeCheck, Camera, CircleCheck, Info, Mail, PenLine, ShieldCheck, UtensilsCrossed } from "lucide-react";
import { navigate } from "../router";
import { reviewsApi } from "../reviews/api";
import { ErrorNote } from "../reviews/ReviewsPage";
import { Stars } from "../reviews/charts";
import type { ProductStats } from "../reviews/types";
import { handOffDraft, studioApi, type CheckChannel, type CopyChannel, type CopyResult, type CopyVariant } from "./api";
import { Citations, CopyButton, PageShell, Segmented, Thinking } from "./shared";

const CHANNELS: { value: CopyChannel; label: string; icon: ReactNode; check: CheckChannel }[] = [
  { value: "instagram", label: "Instagram", icon: <Camera size={15} />, check: "social" },
  { value: "email", label: "Email", icon: <Mail size={15} />, check: "email" },
  { value: "menu_board", label: "Menu board", icon: <UtensilsCrossed size={15} />, check: "menu" },
];

/** The variant as plain text, laid out for its channel (for copying and brand checking). */
function asText(v: CopyVariant, channel: CopyChannel): { text: string; subject: string } {
  if (channel === "email") {
    return { subject: v.headline, text: [v.preheader, v.body, v.cta && `[${v.cta}]`].filter(Boolean).join("\n\n") };
  }
  return { subject: "", text: [v.headline, v.body, v.cta, v.hashtags.join(" ")].filter(Boolean).join("\n\n") };
}

function Preview({ v, channel, product }: { v: CopyVariant; channel: CopyChannel; product: CopyResult["product"] }) {
  if (channel === "instagram") {
    return (
      <div className="preview preview--insta">
        <div className="preview__insta-head">
          <span className="preview__avatar" aria-hidden="true">H</span>
          <strong>honeycrumbbakehouse</strong>
        </div>
        <div className="preview__insta-img" aria-hidden="true">
          {product.name}
        </div>
        <div className="preview__insta-caption">
          <strong>{v.headline}</strong> {v.body}
          {v.cta && <div className="preview__cta-line">{v.cta}</div>}
          {v.hashtags.length > 0 && <div className="preview__tags">{v.hashtags.join(" ")}</div>}
        </div>
      </div>
    );
  }
  if (channel === "email") {
    return (
      <div className="preview preview--email">
        <div className="preview__email-meta">
          <div>
            <span className="muted small">Subject</span> <strong>{v.headline}</strong>{" "}
            <span className={`small ${v.headline.length > 45 ? "bad-text" : "muted"}`}>({v.headline.length}/45)</span>
          </div>
          {v.preheader && (
            <div className="small muted">
              Preheader: {v.preheader} ({v.preheader.length}/90)
            </div>
          )}
        </div>
        <div className="preview__email-body">
          {v.body.split(/\n{2,}/).map((p, i) => (
            <p key={i}>{p}</p>
          ))}
          {v.cta && <span className="preview__button">{v.cta}</span>}
        </div>
      </div>
    );
  }
  return (
    <div className="preview preview--menu">
      <div className="preview__menu-name">{v.headline}</div>
      <div className="preview__menu-price">${product.price.toFixed(2)}</div>
      <p className="preview__menu-desc">{v.body}</p>
      {v.cta && <div className="preview__menu-cta">{v.cta}</div>}
    </div>
  );
}

function VariantCard({ v, index, result }: { v: CopyVariant; index: number; result: CopyResult }) {
  const channel = CHANNELS.find((c) => c.value === result.channel)!;
  const { text, subject } = asText(v, result.channel);
  const plain = subject ? `Subject: ${subject}\n\n${text}` : text;
  return (
    <section className="card variant">
      <div className="card__head">
        <div>
          <div className="small muted">Option {index + 1}</div>
          <h2 className="card__title">{v.angle.charAt(0).toUpperCase() + v.angle.slice(1)}</h2>
        </div>
        <div className="run-row">
          <CopyButton text={plain} />
          <button
            className="btn btn--secondary btn--sm"
            onClick={() => {
              handOffDraft({ text, subject, channel: channel.check });
              navigate("/brand-check");
            }}
          >
            <ShieldCheck size={14} /> Full brand check
          </button>
        </div>
      </div>

      <Preview v={v} channel={result.channel} product={result.product} />

      <div>
        <h3 className="sub-title">
          <BadgeCheck size={15} /> Verified customer quotes
        </h3>
        <ul className="quotes">
          {v.quotes.map((q) => (
            <li key={`${q.review_id}-${q.excerpt}`} className="quote">
              <div className="quote__text">“{q.excerpt}”</div>
              <div className="small muted">
                <Stars value={q.rating} /> {q.customer} · {q.city} · {q.date} · review #{q.review_id}
              </div>
            </li>
          ))}
        </ul>
      </div>

      {v.brand_flags.length > 0 ? (
        <div className="alert alert--warn">
          <AlertTriangle size={16} /> Breaks {v.brand_flags.length} brand rule{v.brand_flags.length > 1 ? "s" : ""}:{" "}
          {v.brand_flags.map((f) => f.problem).join(" ")}
        </div>
      ) : (
        <p className="small ok-text">
          <CircleCheck size={13} /> Passes every automated brand rule.
        </p>
      )}
      <Citations numbers={v.citations} passages={result.passages} />
    </section>
  );
}

export function CopywriterPage() {
  const [products, setProducts] = useState<ProductStats[]>([]);
  const [productId, setProductId] = useState<number | null>(null);
  const [channel, setChannel] = useState<CopyChannel>("instagram");
  const [notes, setNotes] = useState("");
  const [result, setResult] = useState<CopyResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    document.title = "Copywriter · MarketMind";
    reviewsApi
      .products()
      .then((d) => {
        const sorted = [...d.products].sort((a, b) => a.name.localeCompare(b.name));
        setProducts(sorted);
        setProductId((id) => id ?? sorted[0]?.id ?? null);
      })
      .catch(setError);
  }, []);

  const product = products.find((p) => p.id === productId);

  const run = async () => {
    if (productId == null) return;
    setRunning(true);
    setError(null);
    try {
      setResult(await studioApi.generate(productId, channel, notes));
    } catch (e) {
      setError(e);
    } finally {
      setRunning(false);
    }
  };

  return (
    <PageShell title="Copywriter">
      <div className="page-header">
        <h1>Campaign copywriter</h1>
        <p>
          Pick a product and a channel. The AI writes three on-brand options built on what real customers said. Every
          quote is checked word for word against the review it came from, and every option is run through the brand
          rules.
        </p>
      </div>

      <section className="card">
        <div className="form-grid">
          <label className="field">
            <span className="field__label">Product</span>
            <select
              className="input select"
              value={productId ?? ""}
              onChange={(e) => setProductId(Number(e.target.value))}
              disabled={!products.length}
            >
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} {p.availability !== "Year-round" ? `(${p.availability})` : ""}
                </option>
              ))}
            </select>
            {product && (
              <span className="small muted">
                {product.category} · ${product.price.toFixed(2)} · {product.reviews} reviews
                {product.avg_rating != null && <> · {product.avg_rating.toFixed(1)}★</>}
              </span>
            )}
          </label>
          <div className="field">
            <span className="field__label">Channel</span>
            <Segmented value={channel} options={CHANNELS} onChange={setChannel} label="Channel" />
          </div>
        </div>
        <label className="field">
          <span className="field__label">
            Notes <span className="muted small">(optional)</span>
          </span>
          <input
            className="input"
            value={notes}
            maxLength={400}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="e.g. corporate gifting angle, mention same-day pickup"
            onKeyDown={(e) => e.key === "Enter" && run()}
          />
        </label>
        <div className="run-row run-row--start">
          <button className="btn" onClick={run} disabled={running || productId == null}>
            <PenLine size={15} /> {running ? "Writing…" : result ? "Write new options" : "Write copy"}
          </button>
        </div>
      </section>

      <ErrorNote error={error} />
      {running && <Thinking text="Reading reviews and writing on-brand copy…" />}

      {result && !running && (
        <>
          <p className="small muted result-meta">
            <Info size={13} /> {result.product.name} · {CHANNELS.find((c) => c.value === result.channel)!.label} · chosen
            from {result.reviews_offered} positive reviews · {result.model}
          </p>
          {result.availability_note && (
            <div className="alert alert--warn">
              <Info size={16} /> {result.availability_note}
            </div>
          )}
          {result.variants.map((v, i) => (
            <VariantCard key={i} v={v} index={i} result={result} />
          ))}
        </>
      )}
    </PageShell>
  );
}
