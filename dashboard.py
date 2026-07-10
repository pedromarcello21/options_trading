"""
Options Fund Dashboard
=======================
Read-only view of the automated options paper-trading fund. All trading
happens in the background via the news_reporter / economics_reporter /
trading subagents (see .claude/agents/) and the simulator engine — this
dashboard has no controls to place, edit, or cancel trades.

Run with:  streamlit run dashboard.py
"""

from datetime import datetime, date, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from simulator import portfolio as pf_mod

STATE_DIR = Path(__file__).parent / "state"

st.set_page_config(page_title="Options Fund Dashboard", page_icon="🏦", layout="wide")


# ── data loading ─────────────────────────────────────────────────────────────

def load_trade_log() -> pd.DataFrame:
    path = STATE_DIR / "trade_log.csv"
    if not path.exists():
        return pd.DataFrame(columns=pf_mod.TRADE_LOG_FIELDS)
    return pd.read_csv(path)


def load_equity_log() -> pd.DataFrame:
    path = STATE_DIR / "equity_log.csv"
    if not path.exists():
        return pd.DataFrame(columns=pf_mod.EQUITY_LOG_FIELDS)
    df = pd.read_csv(path)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def load_text(name: str) -> str:
    path = STATE_DIR / name
    if not path.exists():
        return "_Not generated yet — waiting on the first agent cycle._"
    return path.read_text()


def days_to_expiry(expiration: str) -> int:
    exp = datetime.strptime(expiration, "%Y-%m-%d").date()
    return (exp - date.today()).days


# ── header ───────────────────────────────────────────────────────────────────

pf = pf_mod.load()

top = st.columns([5, 1])
with top[0]:
    st.title("🏦 Options Fund Dashboard")
    st.caption(
        "Automated by three Claude subagents — news_reporter, economics_reporter, "
        "and trading. This view is read-only; no trades can be placed here."
    )
with top[1]:
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

st.caption(f"Portfolio last updated: {pf.updated_at or 'never'} (UTC)")

# ── top-line metrics ─────────────────────────────────────────────────────────

m = st.columns(6)
m[0].metric("Total equity", f"${pf.equity():,.2f}",
            f"{pf.total_return_pct():+.2f}%")
m[1].metric("Cash", f"${pf.cash:,.2f}")
m[2].metric("Buying power", f"${pf.buying_power():,.2f}")
m[3].metric("Open positions value", f"${pf.positions_value():,.2f}")
m[4].metric("Realized P&L", f"${pf.realized_pnl:+,.2f}")
m[5].metric("Open positions", f"{len(pf.positions)}")

st.divider()

# ── equity curve ─────────────────────────────────────────────────────────────

st.subheader("Equity curve")
equity_df = load_equity_log()
if len(equity_df) >= 2:
    st.line_chart(equity_df.set_index("timestamp")["equity"], use_container_width=True)
else:
    st.info(
        "Not enough history yet for a chart — the equity curve fills in as the "
        "automated cycle runs (`simulator.run_cycle mark`, `trade`, `close`). "
        f"Current equity: ${pf.equity():,.2f}."
    )

st.divider()

# ── tabs: positions / orders / intelligence ─────────────────────────────────

tab_open, tab_pending, tab_closed, tab_intel, tab_log = st.tabs(
    ["📈 Open positions", "⏳ Pending orders", "✅ Closed orders",
     "🧠 Fund intelligence", "📜 Full trade log"]
)

with tab_open:
    if not pf.positions:
        st.info("No open positions.")
    else:
        rows = []
        for p in pf.positions:
            upnl = (p.last_mark - p.entry_price) * pf_mod.MULTIPLIER * p.qty
            rows.append({
                "ID": p.id,
                "Symbol": p.symbol,
                "Side": "Long" if p.qty > 0 else "Short",
                "Type": p.type,
                "Strike": p.strike,
                "Expiration": p.expiration,
                "DTE": days_to_expiry(p.expiration),
                "Contracts": abs(p.qty),
                "Entry price": p.entry_price,
                "Mark": p.last_mark,
                "Unrealized P&L": upnl,
                "Collateral": p.collateral if p.qty < 0 else 0.0,
            })
        df = pd.DataFrame(rows)
        st.dataframe(
            df.style.format({
                "Strike": "${:,.2f}", "Entry price": "${:,.2f}", "Mark": "${:,.2f}",
                "Unrealized P&L": "${:+,.2f}", "Collateral": "${:,.2f}",
            }).map(
                lambda v: "color: #2ecc71" if isinstance(v, (int, float)) and v > 0
                else ("color: #e74c3c" if isinstance(v, (int, float)) and v < 0 else ""),
                subset=["Unrealized P&L"],
            ),
            use_container_width=True, hide_index=True,
        )
        total_upnl = sum(r["Unrealized P&L"] for r in rows)
        st.caption(f"Total unrealized P&L: **${total_upnl:+,.2f}**")

with tab_pending:
    st.info(
        "**0 pending orders.** This simulator executes market orders — the trading "
        "agent's `simulator.run_cycle trade` command fills immediately at the current "
        "model/market price, so there is no resting order queue to display. "
        "(Limit/GTC orders are not implemented.)"
    )

with tab_closed:
    log_df = load_trade_log()
    closed = log_df[log_df["action"].isin(["close", "expire"])].copy() if not log_df.empty else log_df
    if closed.empty:
        st.info("No closed positions yet.")
    else:
        closed["realized_pnl"] = pd.to_numeric(closed["realized_pnl"], errors="coerce")
        closed["note"] = closed["note"].fillna("")
        wins = closed[closed["realized_pnl"] > 0]
        losses = closed[closed["realized_pnl"] < 0]
        total_realized = closed["realized_pnl"].sum()
        win_rate = len(wins) / len(closed) * 100 if len(closed) else 0.0

        s = st.columns(5)
        s[0].metric("Closed trades", len(closed))
        s[1].metric("Win rate", f"{win_rate:.0f}%")
        s[2].metric("Total realized P&L", f"${total_realized:+,.2f}")
        s[3].metric("Avg win", f"${wins['realized_pnl'].mean():,.2f}" if len(wins) else "—")
        s[4].metric("Avg loss", f"${losses['realized_pnl'].mean():,.2f}" if len(losses) else "—")

        display = closed[[
            "timestamp", "action", "symbol", "type", "strike", "expiration",
            "qty", "price", "realized_pnl", "note",
        ]].rename(columns={
            "timestamp": "Closed at", "action": "Action", "symbol": "Symbol",
            "type": "Type", "strike": "Strike", "expiration": "Expiration",
            "qty": "Qty", "price": "Exit price", "realized_pnl": "Realized P&L",
            "note": "Note",
        }).sort_values("Closed at", ascending=False)
        st.dataframe(
            display.style.format({"Strike": "${:,.2f}", "Exit price": "${:,.2f}",
                                  "Realized P&L": "${:+,.2f}"}),
            use_container_width=True, hide_index=True,
        )

with tab_intel:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 📰 Latest news digest")
        st.markdown(load_text("news_digest.md"))
    with c2:
        st.markdown("### 🌐 Latest macro outlook")
        st.markdown(load_text("econ_outlook.md"))

with tab_log:
    log_df = load_trade_log()
    if log_df.empty:
        st.info("No trades recorded yet.")
    else:
        display_log = log_df.fillna("")
        st.dataframe(display_log.sort_values("timestamp", ascending=False),
                     use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "Paper-trading simulator — virtual capital, no real brokerage or real orders. "
    "Educational tool only, not financial advice."
)
