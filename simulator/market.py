"""Market data access with graceful fallbacks.

Every function here is defensive: an automated trading cycle must never hard-fail
because a network call timed out or a ticker was mistyped. When live data is
unavailable we fall back to a Black-Scholes estimate, and failing that, to the
last known value supplied by the caller.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from .pricing import black_scholes, intrinsic

# yfinance is optional at import time so unit tests / offline runs still work.
try:
    import yfinance as yf
except Exception:  # pragma: no cover - environment dependent
    yf = None

DEFAULT_IV = 0.30
DEFAULT_RISK_FREE = 0.045


def _today() -> date:
    return datetime.utcnow().date()


def year_fraction(expiration: str, as_of: Optional[date] = None) -> float:
    """Time to expiry in years (never negative)."""
    as_of = as_of or _today()
    exp = datetime.strptime(expiration, "%Y-%m-%d").date()
    return max((exp - as_of).days, 0) / 365.0


def get_risk_free_rate() -> float:
    if yf is None:
        return DEFAULT_RISK_FREE
    try:
        return float(yf.Ticker("^IRX").fast_info["last_price"]) / 100.0
    except Exception:
        return DEFAULT_RISK_FREE


def get_spot(symbol: str) -> Optional[float]:
    """Latest share price, or None if it cannot be fetched."""
    if yf is None:
        return None
    try:
        price = float(yf.Ticker(symbol).fast_info["last_price"])
        return price if price > 0 else None
    except Exception:
        return None


def _live_option_quote(
    symbol: str, expiration: str, strike: float, option_type: str
) -> Optional[tuple[float, float]]:
    """Try to read a real last price + implied vol off the option chain."""
    if yf is None:
        return None
    try:
        chain = yf.Ticker(symbol).option_chain(expiration)
        table = chain.calls if option_type == "call" else chain.puts
        row = table.loc[table["strike"] == strike]
        if row.empty:
            return None
        row = row.iloc[0]
        price = float(row.get("lastPrice", float("nan")))
        iv = float(row.get("impliedVolatility", float("nan")))
        if not (price >= 0):
            return None
        iv = iv if (iv and iv > 0) else DEFAULT_IV
        return price, iv
    except Exception:
        return None


def get_option_quote(
    symbol: str,
    expiration: str,
    strike: float,
    option_type: str,
    last_known_price: Optional[float] = None,
    last_known_iv: Optional[float] = None,
) -> tuple[float, float, str]:
    """Return (price_per_share, iv, source).

    source is one of: 'market', 'model', 'last', 'intrinsic'. The function never
    raises — the worst case returns the last known price (or intrinsic value).
    """
    iv = last_known_iv if (last_known_iv and last_known_iv > 0) else DEFAULT_IV

    live = _live_option_quote(symbol, expiration, strike, option_type)
    if live is not None:
        price, iv = live
        # A stale/zero last price is common on illiquid strikes; prefer the model.
        if price > 0:
            return price, iv, "market"

    spot = get_spot(symbol)
    t = year_fraction(expiration)
    if spot is not None:
        if t <= 0:
            return intrinsic(option_type, spot, strike), iv, "intrinsic"
        price = black_scholes(
            option_type, spot, strike, t, get_risk_free_rate(), iv
        )
        return max(price, 0.0), iv, "model"

    if last_known_price is not None:
        return last_known_price, iv, "last"

    return 0.0, iv, "last"
