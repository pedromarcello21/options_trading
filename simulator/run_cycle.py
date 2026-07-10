"""Command-line entry point for the options paper-trading simulator.

Usage:
    python -m simulator.run_cycle report
    python -m simulator.run_cycle mark
    python -m simulator.run_cycle trade --symbol AAPL --type call \\
        --strike 200 --expiration 2026-08-21 --qty 1 --side buy
    python -m simulator.run_cycle close --id 1a2b3c4d
    python -m simulator.run_cycle deposit --amount 1000     # rarely needed

The `mark` command is deterministic and side-effect-safe — it is what the CI
heartbeat runs every cycle. The other commands are how the trading agent acts.
"""

from __future__ import annotations

import argparse
import sys

from . import portfolio as pf_mod
from .portfolio import TradeError


def _print_report(pf) -> None:
    print("=" * 60)
    print("  OPTIONS PAPER-TRADING SIMULATOR")
    print("=" * 60)
    print(f"  Cash:            ${pf.cash:>12,.2f}")
    print(f"  Positions value: ${pf.positions_value():>12,.2f}")
    print(f"  Equity:          ${pf.equity():>12,.2f}")
    print(f"  Buying power:    ${pf.buying_power():>12,.2f}")
    print(f"  Realized P&L:    ${pf.realized_pnl:>+12,.2f}")
    print(f"  Total return:    {pf.total_return_pct():>+11.2f}%")
    print("-" * 60)
    if not pf.positions:
        print("  (no open positions)")
    else:
        print(f"  {'id':<9}{'symbol':<7}{'type':<5}{'strike':>8}"
              f"{'exp':>12}{'qty':>5}{'entry':>8}{'mark':>8}{'P&L':>10}")
        for p in pf.positions:
            upnl = (p.last_mark - p.entry_price) * pf_mod.MULTIPLIER * p.qty
            print(f"  {p.id:<9}{p.symbol:<7}{p.type:<5}{p.strike:>8g}"
                  f"{p.expiration:>12}{p.qty:>5}{p.entry_price:>8.2f}"
                  f"{p.last_mark:>8.2f}{upnl:>+10.2f}")
    print("=" * 60)


def cmd_report(args) -> int:
    pf = pf_mod.load()
    _print_report(pf)
    return 0


def cmd_mark(args) -> int:
    pf = pf_mod.load()
    notes = pf_mod.mark_to_market(pf)
    pf_mod.save(pf)
    pf_mod.log_equity_snapshot(pf)
    for n in notes:
        print(f"  · {n}")
    _print_report(pf)
    return 0


def cmd_trade(args) -> int:
    pf = pf_mod.load()
    try:
        pos = pf_mod.open_position(
            pf, symbol=args.symbol, option_type=args.type, strike=args.strike,
            expiration=args.expiration, qty=args.qty, side=args.side,
            price=args.price, note=args.note or "",
        )
    except TradeError as exc:
        print(f"TRADE REJECTED: {exc}", file=sys.stderr)
        return 1
    pf_mod.save(pf)
    pf_mod.log_equity_snapshot(pf)
    print(f"OPENED {args.side} {pos.qty:+d} {pos.symbol} {pos.strike:g} "
          f"{pos.type} @ ${pos.entry_price:.2f}  (id {pos.id})")
    _print_report(pf)
    return 0


def cmd_close(args) -> int:
    pf = pf_mod.load()
    try:
        realized = pf_mod.close_position(pf, args.id, price=args.price, note=args.note or "")
    except TradeError as exc:
        print(f"CLOSE REJECTED: {exc}", file=sys.stderr)
        return 1
    pf_mod.save(pf)
    pf_mod.log_equity_snapshot(pf)
    print(f"CLOSED {args.id}  realized P&L ${realized:+,.2f}")
    _print_report(pf)
    return 0


def cmd_deposit(args) -> int:
    pf = pf_mod.load()
    pf.cash += args.amount
    pf.initial_capital += args.amount
    pf_mod.save(pf)
    print(f"Deposited ${args.amount:,.2f}. Cash now ${pf.cash:,.2f}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="simulator.run_cycle",
                                description="Options paper-trading simulator.")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("report", help="Show portfolio and open positions.")
    sub.add_parser("mark", help="Mark to market + settle expiries (CI-safe).")

    t = sub.add_parser("trade", help="Open an option position.")
    t.add_argument("--symbol", required=True)
    t.add_argument("--type", required=True, choices=["call", "put"])
    t.add_argument("--strike", required=True, type=float)
    t.add_argument("--expiration", required=True, help="YYYY-MM-DD")
    t.add_argument("--qty", required=True, type=int, help="contracts (positive)")
    t.add_argument("--side", required=True, choices=["buy", "sell"])
    t.add_argument("--price", type=float, default=None,
                   help="override fill price per share (else fetched)")
    t.add_argument("--note", default="")

    c = sub.add_parser("close", help="Close a position by id.")
    c.add_argument("--id", required=True)
    c.add_argument("--price", type=float, default=None)
    c.add_argument("--note", default="")

    d = sub.add_parser("deposit", help="Add cash (adjusts cost basis).")
    d.add_argument("--amount", required=True, type=float)

    return p


HANDLERS = {
    "report": cmd_report,
    "mark": cmd_mark,
    "trade": cmd_trade,
    "close": cmd_close,
    "deposit": cmd_deposit,
}


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return HANDLERS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
