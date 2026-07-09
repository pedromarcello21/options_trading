"""Paper-trading portfolio state and mechanics.

Sign convention (used everywhere):
  * qty is signed contracts: +N = long N contracts, -N = short N contracts.
  * One contract controls 100 shares (MULTIPLIER).
  * Opening OR closing cash rule (uniform):   cash -= price * 100 * qty
      - buying a long (qty>0) spends cash; shorting (qty<0) credits premium.
  * Equity:                 cash + Σ(mark * 100 * qty)
      - a short position's mark contributes negatively (a liability).
  * Buying power:           cash - Σ(collateral of open shorts)
      - collateral approximates broker margin: cash-secured.
  * Realized P&L on close:  (exit - entry) * 100 * qty

This is a *simulation*. Short/naked collateral is a simplification, not a real
broker margin model.
"""

from __future__ import annotations

import csv
import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional

from . import market
from .pricing import intrinsic

MULTIPLIER = 100
COMMISSION_PER_CONTRACT = 0.65  # typical retail options commission

_HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.normpath(os.path.join(_HERE, "..", "state"))
PORTFOLIO_PATH = os.path.join(STATE_DIR, "portfolio.json")
TRADE_LOG_PATH = os.path.join(STATE_DIR, "trade_log.csv")
EQUITY_LOG_PATH = os.path.join(STATE_DIR, "equity_log.csv")

TRADE_LOG_FIELDS = [
    "timestamp",
    "action",
    "id",
    "symbol",
    "type",
    "strike",
    "expiration",
    "qty",
    "price",
    "cash_delta",
    "commission",
    "realized_pnl",
    "note",
]

EQUITY_LOG_FIELDS = [
    "timestamp",
    "cash",
    "positions_value",
    "equity",
    "buying_power",
    "realized_pnl",
    "total_return_pct",
    "open_positions",
]


@dataclass
class Position:
    id: str
    symbol: str
    type: str  # "call" | "put"
    strike: float
    expiration: str  # YYYY-MM-DD
    qty: int  # signed contracts
    entry_price: float  # per share
    opened_at: str
    iv: float = market.DEFAULT_IV
    last_mark: float = 0.0
    collateral: float = 0.0

    def market_value(self) -> float:
        """Signed mark-to-market value (asset if long, liability if short)."""
        return self.last_mark * MULTIPLIER * self.qty


@dataclass
class Portfolio:
    cash: float = 5000.0
    initial_capital: float = 5000.0
    realized_pnl: float = 0.0
    created_at: str = ""
    updated_at: str = ""
    positions: list[Position] = field(default_factory=list)

    # ── derived metrics ──────────────────────────────────────────────────────
    def positions_value(self) -> float:
        return sum(p.market_value() for p in self.positions)

    def equity(self) -> float:
        return self.cash + self.positions_value()

    def reserved_collateral(self) -> float:
        return sum(p.collateral for p in self.positions if p.qty < 0)

    def buying_power(self) -> float:
        return self.cash - self.reserved_collateral()

    def total_return_pct(self) -> float:
        if self.initial_capital == 0:
            return 0.0
        return (self.equity() - self.initial_capital) / self.initial_capital * 100.0


# ── persistence ──────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path: str = PORTFOLIO_PATH) -> Portfolio:
    if not os.path.exists(path):
        pf = Portfolio(created_at=_now(), updated_at=_now())
        save(pf, path)
        return pf
    with open(path, "r") as fh:
        raw = json.load(fh)
    positions = [Position(**p) for p in raw.pop("positions", [])]
    return Portfolio(positions=positions, **raw)


def save(pf: Portfolio, path: str = PORTFOLIO_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pf.updated_at = _now()
    data = asdict(pf)
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def _append_log(row: dict, path: str = TRADE_LOG_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    exists = os.path.exists(path)
    with open(path, "a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=TRADE_LOG_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in TRADE_LOG_FIELDS})


def log_equity_snapshot(pf: Portfolio, path: str = EQUITY_LOG_PATH) -> None:
    """Append a point-in-time equity snapshot, for the dashboard's equity curve."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    exists = os.path.exists(path)
    with open(path, "a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=EQUITY_LOG_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({
            "timestamp": _now(),
            "cash": round(pf.cash, 2),
            "positions_value": round(pf.positions_value(), 2),
            "equity": round(pf.equity(), 2),
            "buying_power": round(pf.buying_power(), 2),
            "realized_pnl": round(pf.realized_pnl, 2),
            "total_return_pct": round(pf.total_return_pct(), 4),
            "open_positions": len(pf.positions),
        })


# ── collateral / risk ────────────────────────────────────────────────────────

def _collateral_for_short(option_type: str, strike: float, qty: int,
                          spot: Optional[float]) -> float:
    """Cash-secured collateral for a short position (qty < 0)."""
    n = abs(qty)
    if option_type == "put":
        # Cash-secured put: enough to buy the shares if assigned.
        return strike * MULTIPLIER * n
    # Short call: reserve the notional value of the underlying (approx).
    ref = spot if (spot and spot > 0) else strike
    return ref * MULTIPLIER * n


# ── trading operations ───────────────────────────────────────────────────────

class TradeError(Exception):
    """Raised when a trade cannot be executed (bad input or insufficient funds)."""


def open_position(
    pf: Portfolio,
    symbol: str,
    option_type: str,
    strike: float,
    expiration: str,
    qty: int,
    side: str,
    price: Optional[float] = None,
    note: str = "",
) -> Position:
    """Open a new option position. side is 'buy' (long) or 'sell' (short)."""
    option_type = option_type.lower()
    if option_type not in ("call", "put"):
        raise TradeError(f"option_type must be call/put, got {option_type!r}")
    side = side.lower()
    if side not in ("buy", "sell"):
        raise TradeError(f"side must be buy/sell, got {side!r}")
    if qty <= 0:
        raise TradeError("qty must be a positive number of contracts")

    signed_qty = qty if side == "buy" else -qty
    spot = market.get_spot(symbol)

    if price is None:
        price, iv, _src = market.get_option_quote(symbol, expiration, strike, option_type)
    else:
        _p, iv, _src = market.get_option_quote(symbol, expiration, strike, option_type)
    if price <= 0:
        raise TradeError(
            f"Could not determine a price for {symbol} {strike} {option_type}; "
            "pass --price to override."
        )

    commission = COMMISSION_PER_CONTRACT * qty
    cash_delta = -(price * MULTIPLIER * signed_qty) - commission
    collateral = _collateral_for_short(option_type, strike, signed_qty, spot) if signed_qty < 0 else 0.0

    # Simulate applying the trade, then verify buying power stays non-negative.
    projected_cash = pf.cash + cash_delta
    projected_collateral = pf.reserved_collateral() + collateral
    if projected_cash - projected_collateral < 0:
        raise TradeError(
            f"Insufficient buying power. Need cash≥{collateral - (cash_delta):.2f} "
            f"beyond reserves; available buying power ${pf.buying_power():,.2f}."
        )

    pos = Position(
        id=uuid.uuid4().hex[:8],
        symbol=symbol.upper(),
        type=option_type,
        strike=float(strike),
        expiration=expiration,
        qty=signed_qty,
        entry_price=float(price),
        opened_at=_now(),
        iv=float(iv),
        last_mark=float(price),
        collateral=float(collateral),
    )
    pf.cash = projected_cash
    pf.positions.append(pos)

    _append_log({
        "timestamp": _now(), "action": f"open_{side}", "id": pos.id,
        "symbol": pos.symbol, "type": pos.type, "strike": pos.strike,
        "expiration": pos.expiration, "qty": signed_qty, "price": price,
        "cash_delta": round(cash_delta, 2), "commission": commission, "note": note,
    })
    return pos


def close_position(
    pf: Portfolio,
    position_id: str,
    price: Optional[float] = None,
    note: str = "",
) -> float:
    """Close a position at `price` (or current mark). Returns realized P&L."""
    pos = next((p for p in pf.positions if p.id == position_id), None)
    if pos is None:
        raise TradeError(f"No open position with id {position_id!r}")

    if price is None:
        price, _iv, _src = market.get_option_quote(
            pos.symbol, pos.expiration, pos.strike, pos.type,
            last_known_price=pos.last_mark, last_known_iv=pos.iv,
        )
    commission = COMMISSION_PER_CONTRACT * abs(pos.qty)
    # Closing reverses the position: cash += price*100*qty (uniform rule with -qty).
    cash_delta = price * MULTIPLIER * pos.qty - commission
    realized = (price - pos.entry_price) * MULTIPLIER * pos.qty - commission

    pf.cash += cash_delta
    pf.realized_pnl += realized
    pf.positions = [p for p in pf.positions if p.id != position_id]

    _append_log({
        "timestamp": _now(), "action": "close", "id": pos.id,
        "symbol": pos.symbol, "type": pos.type, "strike": pos.strike,
        "expiration": pos.expiration, "qty": -pos.qty, "price": price,
        "cash_delta": round(cash_delta, 2), "commission": commission,
        "realized_pnl": round(realized, 2), "note": note,
    })
    return realized


def mark_to_market(pf: Portfolio) -> list[str]:
    """Refresh every position's mark; settle expired ones at intrinsic value.

    Returns a list of human-readable notes about anything that changed.
    """
    notes: list[str] = []
    today = market._today()

    for pos in list(pf.positions):
        expiry = datetime.strptime(pos.expiration, "%Y-%m-%d").date()

        if expiry <= today:
            spot = market.get_spot(pos.symbol)
            settle = intrinsic(pos.type, spot, pos.strike) if spot is not None else pos.last_mark
            realized = (settle - pos.entry_price) * MULTIPLIER * pos.qty
            cash_delta = settle * MULTIPLIER * pos.qty
            pf.cash += cash_delta
            pf.realized_pnl += realized
            pf.positions = [p for p in pf.positions if p.id != pos.id]
            _append_log({
                "timestamp": _now(), "action": "expire", "id": pos.id,
                "symbol": pos.symbol, "type": pos.type, "strike": pos.strike,
                "expiration": pos.expiration, "qty": -pos.qty, "price": settle,
                "cash_delta": round(cash_delta, 2), "commission": 0,
                "realized_pnl": round(realized, 2),
                "note": f"settled at intrinsic value ${settle:.2f}",
            })
            notes.append(
                f"{pos.symbol} {pos.strike:g} {pos.type} expired → "
                f"settled ${settle:.2f} (realized {realized:+.2f})"
            )
            continue

        price, iv, src = market.get_option_quote(
            pos.symbol, pos.expiration, pos.strike, pos.type,
            last_known_price=pos.last_mark, last_known_iv=pos.iv,
        )
        pos.last_mark = float(price)
        pos.iv = float(iv)
        notes.append(f"{pos.symbol} {pos.strike:g} {pos.type} mark=${price:.2f} ({src})")

    return notes
