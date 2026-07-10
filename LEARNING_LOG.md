# Learning Log

A running log of the technologies, system design, and technical concepts used
in this project — captured to deepen understanding, not just track changes.
Newest entries at the top.

---

## 2026-06-26 — Modernizing a defunct options trading Streamlit app

### Technologies used
- **yfinance** — a Python wrapper around Yahoo Finance's unofficial API. The original app used `yahoo_fin`, which scraped Yahoo pages that no longer exist; `yfinance` is actively maintained and provides the same data (live quotes, option chains, dividends) through a more stable interface. Key methods used: `Ticker.fast_info["last_price"]`, `Ticker.options` (expiration dates), `Ticker.option_chain(date)` (returns `.calls` and `.puts` DataFrames).
- **Streamlit** — a Python framework that turns a plain script into an interactive web app. It reruns the entire script top-to-bottom whenever the user changes an input widget. The original app used a deprecated `st.set_option('deprecation.showPyplotGlobalUse', False)` call that crashes on modern Streamlit — removed in the rebuild.
- **`st.cache_data`** — Streamlit's caching decorator. Because the script reruns on every UI interaction, without caching every keystroke would trigger a live API call to Yahoo Finance. `ttl=900` means the cache expires after 15 minutes, so data stays fresh without hammering the API.
- **Black-Scholes Model (hand-written)** — the industry-standard formula for pricing European options. The original app used the `optionprice` library for this. The rebuild implements it directly (~20 lines of math) using only Python's standard `math` module, eliminating a fragile dependency. The formula depends on: spot price, strike, time to expiry (in years), risk-free rate, implied volatility, and dividend yield.
- **`^IRX` (13-week T-bill via yfinance)** — the risk-free rate input to Black-Scholes. The original app scraped a hardcoded 2023 Treasury URL, meaning it priced options with stale rates. `^IRX` is a live ticker for the 3-month T-bill yield, so the model always uses a current rate.
- **matplotlib** — used to draw the payoff diagram. The original app used `opstrat`, a niche unmaintained library that wrapped matplotlib anyway. Going direct gives more control and removes the dependency.

### System design

```
User (sidebar inputs)
        │
        ▼
  yfinance API ──► spot price, expiration dates, option chain (calls/puts)
        │                       │
        │                  ^IRX ticker ──► live risk-free rate
        │
        ▼
  Black-Scholes (hand-written)
  ├── call price
  └── put price
        │
        ▼
  P/L calculator
  ├── P/L table (7 price scenarios: -30% to +30%)
  └── Payoff chart (200-point price grid, matplotlib)
        │
        ▼
  Streamlit renders: summary table, P/L table, payoff chart
```

All data fetching functions are wrapped in `@st.cache_data` — the results are memoized so reruns from widget interactions don't re-hit the API.

### Key concepts to understand

- **Black-Scholes Model** — prices a European option (one that can only be exercised at expiry, not before). The key inputs are spot price (S), strike (K), time to expiry in years (T), risk-free rate (r), and implied volatility (σ). It outputs a theoretical "fair" price. Worth reading: the Wikipedia article covers the formula derivation; the key insight is that it models stock price as a random walk (geometric Brownian motion).
- **Implied Volatility (IV)** — the market's forward-looking guess at how much the stock will move. `yfinance` returns it as a decimal on each option row (e.g. `0.35` = 35%). The original app parsed it from a percentage string — the new app reads it directly. IV is *derived* from the market price of an option by inverting Black-Scholes, so it reflects collective market sentiment rather than historical data.
- **Option payoff at expiry** — a call is worth `max(spot - strike, 0)` at expiry; a put is worth `max(strike - spot, 0)`. Subtract the premium paid (the option price) to get P/L for a long position. Flip the sign for a short (sold) position.
- **Git branching for project lifecycle** — three branches capture three states of the project: `deprecated` (original frozen app), `main` (clean base), `beta` (active development). This lets you always `git checkout deprecated` to see the original code without losing the new work.

### Trade-offs & decisions

- **Hand-written BSM vs. a library like `py_vollib`** — chose hand-written because it removes a dependency for ~20 lines of stable math that hasn't changed in 50 years. `py_vollib` adds IV-solving (Newton-Raphson inversion) which isn't needed here since `yfinance` provides IV directly.
- **`yfinance` over `yahoo_fin`** — `yahoo_fin` is unmaintained and its scraping broke when Yahoo changed their site. `yfinance` uses Yahoo's unofficial API endpoints more robustly and has active maintenance.
- **`@st.cache_data` TTL of 900s (15 min)** — balances freshness vs. API load. Option chains don't tick second-by-second for most use cases, so 15 minutes is a reasonable staleness tolerance.

### Open questions / to explore
- How would you add **IV skew** visualization? Right now the app prices call and put at a single strike's IV; a skew chart would plot IV across all strikes for the chosen expiration.
- Could replace the static payoff chart with **Plotly** for interactivity (hover to see exact P/L values).
- How does **American option pricing** differ? Black-Scholes is for European options; U.S. equity options are American (exercisable any time), so BSM is an approximation here.
