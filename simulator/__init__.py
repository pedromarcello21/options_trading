"""Options paper-trading simulator.

A self-contained engine that manages a virtual options portfolio (starting at
$5,000). Trades are *simulated* — no real brokerage, no real money. Market data
is pulled from public sources (yfinance) with graceful fallbacks so the engine
never hard-fails during an automated cycle.
"""

__all__ = ["pricing", "market", "portfolio", "run_cycle"]
