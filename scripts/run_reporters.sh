#!/usr/bin/env bash
# Run news_reporter and economics_reporter to refresh the fund's intelligence.
#
# Recommended cadence: weekly (manual). No ANTHROPIC_API_KEY needed — this
# rides your existing local Claude Code login, the same as running `claude`
# interactively.
#
# Usage:  ./scripts/run_reporters.sh

set -uo pipefail
cd "$(dirname "$0")/.."

echo "== news_reporter =="
claude -p --agent news_reporter \
  "Refresh state/news_digest.md for this cycle. Read your memory, check the watchlist and current portfolio, research current news for the watchlist tickers, write the digest, and update your memory." \
  --permission-mode acceptEdits \
  --allowedTools "Read,Grep,Glob,WebSearch,WebFetch,Write" \
  || echo "news_reporter failed — digest may be stale."

echo
echo "== economics_reporter =="
claude -p --agent economics_reporter \
  "Refresh state/econ_outlook.md for this cycle. Read your memory, research the current macro picture, write the outlook, and update your memory." \
  --permission-mode acceptEdits \
  --allowedTools "Read,Grep,Glob,WebSearch,WebFetch,Write" \
  || echo "economics_reporter failed — outlook may be stale."

echo
echo "Done. Digests: state/news_digest.md, state/econ_outlook.md"
