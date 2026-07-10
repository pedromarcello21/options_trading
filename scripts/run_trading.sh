#!/usr/bin/env bash
# Run the trading agent: reviews the book against the latest digests and
# executes any trades via the simulator CLI.
#
# Recommended cadence: monthly (manual), or whenever you want a trading
# decision made. Run ./scripts/run_reporters.sh first (or recently enough)
# so the digests it reads aren't stale. No ANTHROPIC_API_KEY needed — this
# rides your existing local Claude Code login.
#
# Usage:  ./scripts/run_trading.sh

set -euo pipefail
cd "$(dirname "$0")/.."

echo "== trading =="
claude -p --agent trading \
  "Review the current book against state/news_digest.md and state/econ_outlook.md, execute any trades via 'python -m simulator.run_cycle' per your risk rules, and update your memory with today's desk note." \
  --permission-mode acceptEdits \
  --allowedTools "Read,Write,Edit,Grep,Glob,WebSearch,WebFetch,Bash(python -m simulator.run_cycle:*)"

echo
echo "Done. Check the dashboard (streamlit run dashboard.py) or state/portfolio.json for the result."
