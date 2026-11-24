/** Honeycrumb "crumb" mark: a croissant curled inside a honeycomb cell. */
export function LogoMark({ size = 36 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <defs>
        <linearGradient id="hc-logo" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#C57A3D" />
          <stop offset="1" stopColor="#A9533E" />
        </linearGradient>
      </defs>
      <path d="M32 3l25 14.5v29L32 61 7 46.5v-29z" fill="url(#hc-logo)" />
      <path
        d="M16 37c3-9 9-14 16-14s13 5 16 14c-4-3-7-3-9-1-2-3-4.5-4-7-4s-5 1-7 4c-2-2-5-2-9 1z"
        fill="#F5F1EE"
      />
      <path d="M26 31l2 6M32 29v7M38 31l-2 6" stroke="#A9533E" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function Logo() {
  return (
    <div className="logo">
      <LogoMark />
      <div>
        <div className="logo__name">Honeycrumb</div>
        <div className="logo__tag">MarketMind · Marketing Assistant</div>
      </div>
    </div>
  );
}
