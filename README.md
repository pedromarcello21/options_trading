# Options Trading Simulator 🏦

A self-sufficient **options paper-trading simulator** run by a small team of
Claude subagents acting as a hedge fund. A virtual **$5,000** account is managed
on an ongoing, automatable basis: research agents gather the latest news and
macro data, and a trading agent uses it to open and close (simulated) options
positions.

> **This is a simulator.** No real brokerage, no real money, no real orders.
> Market data is public (via `yfinance`); fills are simulated at model/last
> prices. Educational use only — not financial advice.

> The original **Options Payoff Forecaster** (Streamlit app, `app.py`) is
> preserved as-is on the [`vibe`](../../tree/vibe) branch.

## Dashboard (`dashboard.py`)

A **read-only** Streamlit dashboard — the only thing a user is meant to look at
day to day. All trading happens in the background via the subagents; this view
has no controls to place, edit, or cancel trades.

```bash
streamlit run dashboard.py
```

It shows:
- **Top-line metrics** — total equity, cash, buying power, open-positions value,
  realized P&L, total return %.
- **Equity curve** — built from `state/equity_log.csv`, a snapshot appended on
  every `mark` / `trade` / `close`.
- **Open positions** — live marks and unrealized P&L per position.
- **Pending orders** — always 0: this engine only supports market orders, which
  fill immediately when the trading agent calls the CLI, so there's no resting
  order queue.
- **Closed orders** — realized P&L per trade plus win rate / avg win / avg loss,
  sourced from `state/trade_log.csv`.
- **Fund intelligence** — the latest `news_digest.md` and `econ_outlook.md`
  produced by the reporter agents.
- **Full trade log** — every open/close/expire event, unfiltered.

## The agent team (`.claude/agents/`)

| Agent | Access | Role |
|-------|--------|------|
| `news_reporter` | read + research, writes only its digest/memory | Latest market & company news → `state/news_digest.md` |
| `economics_reporter` | read + research, writes only its outlook/memory | Rates, inflation, Fed, jobs, vol → `state/econ_outlook.md` |
| `trading` | full access | Reads both digests + portfolio, executes options trades via the CLI |

The reporters have **no Bash/Edit** tools, so they can never run the trade engine
or touch the portfolio — only the `trading` agent can. Each agent keeps a memory
file in `.claude/agents/memory/` so it persists across sessions.

## The engine (`simulator/`)

A dependency-light Python engine that manages the portfolio and prices options
with Black-Scholes.

```
simulator/
  pricing.py    # Black-Scholes + intrinsic value
  market.py     # yfinance data with graceful offline fallbacks
  portfolio.py  # signed-qty positions, cash, buying power, mark-to-market
  run_cycle.py  # CLI: report | mark | trade | close | deposit
state/
  portfolio.json   # the $5,000 account (committed state)
  trade_log.csv    # append-only trade history (realized P&L per close/expire)
  equity_log.csv   # equity snapshots over time, feeds the dashboard's chart
  news_digest.md   # produced by news_reporter
  econ_outlook.md  # produced by economics_reporter
```

### CLI

```bash
# Show the book
python -m simulator.run_cycle report

# Mark to market + settle expiries (deterministic; the CI heartbeat)
python -m simulator.run_cycle mark

# Open a long call (pay premium)
python -m simulator.run_cycle trade --symbol AAPL --type call \
    --strike 200 --expiration 2026-08-21 --qty 1 --side buy

# Sell a cash-secured put (collect premium, reserves collateral)
python -m simulator.run_cycle trade --symbol MSFT --type put \
    --strike 400 --expiration 2026-08-21 --qty 1 --side sell

# Close a position by id
python -m simulator.run_cycle close --id 1a2b3c4d
```

`--side buy` = long, `--side sell` = short. Add `--price X` to override the
fetched fill price. One contract = 100 shares; a $0.65/contract commission is
applied. Short positions reserve **cash-secured collateral** and opens are
rejected if buying power would go negative.

### Accounting model (signed quantity)

- `qty` is signed contracts (+long / −short).
- Open **or** close cash rule: `cash -= price * 100 * qty`.
- Equity: `cash + Σ(mark * 100 * qty)` (shorts are a liability).
- Buying power: `cash − Σ(collateral of open shorts)`.
- Realized P&L on close/expiry: `(exit − entry) * 100 * qty`.

## Automation (`.github/workflows/trading-cycle.yml`)

A scheduled GitHub Action runs a cycle on weekday mornings (and on demand):

1. **Always** runs `run_cycle mark` — values the book, settles expiries, no
   secrets required.
2. **If** an `ANTHROPIC_API_KEY` secret is set, it installs the Claude Code CLI
   and runs the full agent pipeline (news → economics → trading).
3. Commits any changes to `state/` and the agents' memory back to `beta`.

**To enable the agent pipeline:**
- Repo **Settings → Secrets and variables → Actions** → add `ANTHROPIC_API_KEY`.
- Repo **Settings → Actions → General → Workflow permissions** → *Read and write*.

Without the key, the deterministic heartbeat still runs every cycle.

## Running a full cycle locally

With Claude Code installed, from the repo root:

```
claude -p "Run one trading cycle: news_reporter, then economics_reporter, then
the trading agent. Each updates its own memory."
```

Or drive the pieces manually: run the agents, then use the CLI above.

## Setup

```bash
pip install -r requirements.txt
python -m simulator.run_cycle report   # confirms a fresh $5,000 account
streamlit run dashboard.py             # view the fund dashboard
```

## Caveats

- Short/naked-option collateral is a **simplified cash-secured model**, not a
  real broker's margin system.
- Black-Scholes assumes European exercise and constant volatility — prices are
  approximations.
- The CI Claude step consumes API credits.
