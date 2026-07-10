# Trading Desk — Memory

_Persistent strategy + journal for the trading agent. Read at the start of every
cycle, update at the end. This is the fund's institutional memory._

## Mandate
- Grow a virtual **$5,000** options account. Paper trading only.
- Risk: ≤ ~20% of equity per new position; keep ≥ 15% cash buffer; prefer
  defined-risk; avoid naked short calls.

## Current strategy / stance
- Net-long-delta, long-vol. Bullish AI/semis momentum via long calls, balanced
  with an index put hedge into CPI (7/14) & FOMC (7/28-29). Macro: uptrend
  intact but fragile/complacent — VIX ~17 & tight HY spreads look cheap vs
  Iran/oil + stagflation tail risk. Own optionality > sell premium here.
- ~41% deployed in premium, ~59% cash.

## Structural note
- The sim reserves FULL NOTIONAL collateral on short options (put=strike*100,
  call=spot*100) → premium-selling/spreads are infeasible on a $5k account.
  Toolkit in practice = long options only.

## Open theses (one line per position)
- `0c2c8985` AAPL 320C 8/21 @ $10.30 — bullish tech; Broadcom $30B ASIC deal +
  JPM PT $345; 7/30 earnings (Cook's last call) convexity. Target +50-100%
  through ~$335; cut ~-50% / below ~$300.
- `cbccf9ae` NVDA 220C 8/21 @ $4.99 — semis momentum; -18% off highs, Blackwell
  sold out. 8/26 earnings are AFTER expiry → momentum play, not an earnings
  hold. Cut ~-60%.
- `25fd6c2c` SPY 720P 8/21 @ $5.08 — tail hedge into CPI/FOMC; insurance,
  expected to lose value if the tape stays calm. Cut/roll after FOMC if unused.

## Lessons learned
- Fill price reveals spot: buy 1 contract, read the fill, then size the rest.
  (AAPL 320C filled ~$10.30, implying spot ~$310.)
- Enforce the 20% single-position cap mechanically: closed an oversized NVDA
  200C (26% of equity) for -$0.65 and reopened OTM at 220 (10%) instead.
- Short options are off the table on this account size — build with longs.

## Journal
- 2026-07-10 — Opened the book from all-cash. Bullish AI/semis backdrop but a
  fragile/complacent tape → net-long, long-vol posture. Bought AAPL 320C,
  NVDA 220C, SPY 720P hedge. Re-struck NVDA 200→220 to respect the 20% cap
  (-$0.65 realized). Equity $4,996.75, cash $2,959.75 (~59%). Watching: CPI
  7/14, Iran/oil headlines, MSFT 7/29, AAPL 7/30, FOMC 7/28-29.
