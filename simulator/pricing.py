"""Black-Scholes option pricing (no external dependency).

Reused from the Options Payoff Forecaster (app.py). European exercise, constant
volatility — an approximation, good enough for a simulator.
"""

from __future__ import annotations

from math import erf, exp, log, sqrt


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def intrinsic(option_type: str, spot: float, strike: float) -> float:
    """Value of the option if it expired right now."""
    if option_type == "call":
        return max(spot - strike, 0.0)
    return max(strike - spot, 0.0)


def black_scholes(
    option_type: str,
    spot: float,
    strike: float,
    t_years: float,
    rate: float,
    sigma: float,
    div_yield: float = 0.0,
) -> float:
    """Theoretical price of a European call/put per share.

    Falls back to intrinsic value when there is no time or no volatility left.
    """
    if t_years <= 0 or sigma <= 0:
        return intrinsic(option_type, spot, strike)

    d1 = (log(spot / strike) + (rate - div_yield + 0.5 * sigma**2) * t_years) / (
        sigma * sqrt(t_years)
    )
    d2 = d1 - sigma * sqrt(t_years)

    if option_type == "call":
        return spot * exp(-div_yield * t_years) * _norm_cdf(d1) - strike * exp(
            -rate * t_years
        ) * _norm_cdf(d2)
    return strike * exp(-rate * t_years) * _norm_cdf(-d2) - spot * exp(
        -div_yield * t_years
    ) * _norm_cdf(-d1)
