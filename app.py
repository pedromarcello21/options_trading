"""
Options Payoff Forecaster
=========================
A modernized rebuild of my first-ever app.

Run with:  streamlit run app.py
"""

from datetime import datetime
from math import erf, exp, log, sqrt

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf


# ── Black-Scholes (no external dependency) ──────────────────────────────────

def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def black_scholes(option_type, spot, strike, t_years, rate, sigma, div_yield=0.0):
    if t_years <= 0 or sigma <= 0:
        intrinsic = spot - strike if option_type == "call" else strike - spot
        return max(intrinsic, 0.0)
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


# ── Data fetching (cached) ───────────────────────────────────────────────────

@st.cache_data(ttl=900, show_spinner=False)
def get_spot_and_expirations(symbol):
    tk = yf.Ticker(symbol)
    spot = float(tk.fast_info["last_price"])
    return spot, list(tk.options)


@st.cache_data(ttl=900, show_spinner=False)
def get_option_chain(symbol, expiration):
    chain = yf.Ticker(symbol).option_chain(expiration)
    return chain.calls, chain.puts


@st.cache_data(ttl=3600, show_spinner=False)
def get_risk_free_rate():
    try:
        return float(yf.Ticker("^IRX").fast_info["last_price"]) / 100.0
    except Exception:
        return 0.045


# ── Payoff math ──────────────────────────────────────────────────────────────

def pnl_at_expiry(option_type, premium, strike, price_at_expiry, shares, sign):
    if option_type == "call":
        intrinsic = max(price_at_expiry - strike, 0.0)
    else:
        intrinsic = max(strike - price_at_expiry, 0.0)
    return sign * (intrinsic - premium) * shares


def _safe_iv(value):
    try:
        iv = float(value)
        return iv if np.isfinite(iv) and iv > 0 else 0.30
    except (TypeError, ValueError):
        return 0.30


# ── UI ───────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Options Payoff Forecaster", page_icon="📈", layout="wide")
st.title("📈 Options Payoff Forecaster")
st.caption("Live option chains · Black-Scholes pricing · P/L at expiration")

with st.sidebar:
    st.header("Inputs")
    symbol = st.text_input("Stock ticker", value="AAPL").strip().upper()
    contracts = st.number_input("Contracts (×100 shares)", min_value=1, value=1, step=1)
    position = st.radio("Position", ["Long (buy)", "Short (sell)"], horizontal=True)
    sign = 1 if position.startswith("Long") else -1

    st.divider()
    st.caption("Model assumptions")
    rate = st.number_input(
        "Risk-free rate (%)", value=round(get_risk_free_rate() * 100, 2), step=0.25
    ) / 100.0
    div_yield = st.number_input("Dividend yield (%)", value=0.0, step=0.25) / 100.0

if not symbol:
    st.info("Enter a ticker in the sidebar to begin.")
    st.stop()

# Load spot price + expiration dates
try:
    spot, expirations = get_spot_and_expirations(symbol)
except Exception as exc:
    st.error(f"Couldn't load data for **{symbol}**. Double-check the ticker. ({exc})")
    st.stop()

if not expirations:
    st.warning(f"**{symbol}** doesn't appear to have listed options.")
    st.stop()

# Top row: spot, expiration picker, strike picker
col1, col2, col3 = st.columns(3)
col1.metric("Spot price", f"${spot:,.2f}")
expiration = col2.selectbox("Expiration date", expirations)

# Load option chain
try:
    calls, puts = get_option_chain(symbol, expiration)
except Exception as exc:
    st.error(f"Couldn't load the option chain for {expiration}. ({exc})")
    st.stop()

strikes = sorted(set(calls["strike"]).intersection(puts["strike"]))
if not strikes:
    st.warning("No overlapping call/put strikes for this expiration.")
    st.stop()

default_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot))
strike = col3.selectbox("Strike price", strikes, index=default_idx)

# Time to expiry
expiry_date = datetime.strptime(expiration, "%Y-%m-%d").date()
days = max((expiry_date - datetime.today().date()).days, 0)
t_years = days / 365.0

# Implied vol for chosen strike
call_row = calls.loc[calls["strike"] == strike].iloc[0]
put_row = puts.loc[puts["strike"] == strike].iloc[0]
call_iv = _safe_iv(call_row.get("impliedVolatility"))
put_iv = _safe_iv(put_row.get("impliedVolatility"))

# BSM prices
call_price = black_scholes("call", spot, strike, t_years, rate, call_iv, div_yield)
put_price = black_scholes("put", spot, strike, t_years, rate, put_iv, div_yield)
shares = 100 * contracts

st.divider()
st.subheader(f"{symbol}  ·  ${strike:g} strike  ·  expires {expiration}  ·  {days} days out")

# Summary table
summary = pd.DataFrame(
    {
        "Black-Scholes price": [f"${call_price:.2f}", f"${put_price:.2f}"],
        "Market last price": [
            f"${float(call_row.get('lastPrice', float('nan'))):.2f}",
            f"${float(put_row.get('lastPrice', float('nan'))):.2f}",
        ],
        "Implied volatility": [f"{call_iv:.1%}", f"{put_iv:.1%}"],
    },
    index=["Call", "Put"],
)
st.dataframe(summary, use_container_width=True)

# P/L table
moves = [-0.30, -0.20, -0.10, 0.0, 0.10, 0.20, 0.30]
rows = []
for m in moves:
    s_t = spot * (1 + m)
    c_pl = pnl_at_expiry("call", call_price, strike, s_t, shares, sign)
    p_pl = pnl_at_expiry("put", put_price, strike, s_t, shares, sign)
    rows.append({
        "% Change": f"{m:+.0%}",
        "Price at expiry": s_t,
        "Call P/L": c_pl,
        "Put P/L": p_pl,
        "Combined P/L": c_pl + p_pl,
    })

pl_table = pd.DataFrame(rows).set_index("% Change")
st.markdown("**Profit / loss at expiration**")
st.dataframe(
    pl_table.style.format({
        "Price at expiry": "${:,.2f}",
        "Call P/L": "${:,.0f}",
        "Put P/L": "${:,.0f}",
        "Combined P/L": "${:,.0f}",
    }),
    use_container_width=True,
)

# Payoff chart
price_grid = np.linspace(spot * 0.5, spot * 1.5, 200)
call_curve = [pnl_at_expiry("call", call_price, strike, s, shares, sign) for s in price_grid]
put_curve  = [pnl_at_expiry("put",  put_price,  strike, s, shares, sign) for s in price_grid]
combined   = np.array(call_curve) + np.array(put_curve)

fig, ax = plt.subplots(figsize=(9, 5))
ax.plot(price_grid, call_curve, label="Call",     linewidth=2)
ax.plot(price_grid, put_curve,  label="Put",      linewidth=2)
ax.plot(price_grid, combined,   label="Combined", linewidth=2, linestyle="--")
ax.axhline(0,    color="black", linewidth=0.8)
ax.axvline(spot, color="grey",  linewidth=0.8, linestyle=":", label="Spot")
ax.set_title(f"{position} payoff at expiry — {symbol} ${strike:g} strike")
ax.set_xlabel("Share price at expiration ($)")
ax.set_ylabel("Profit / loss ($)")
ax.legend()
ax.grid(alpha=0.3)
st.pyplot(fig)

st.caption(
    "Educational tool only — not financial advice. Black-Scholes assumes European exercise "
    "and constant volatility; prices are approximations."
)
