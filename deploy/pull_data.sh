#!/usr/bin/env bash
# Run on your laptop: copy recorded data + server results back for local backtests/dashboard.
#   deploy/pull_data.sh ubuntu@<server-ip>
set -euo pipefail
HOST=${1:?usage: deploy/pull_data.sh user@host}
cd "$(dirname "$0")/.."
rsync -az --partial "$HOST:kalshi-data/raw/" ~/kalshi-data/raw/
rsync -az "$HOST:kalshi/results/" results/
echo "pulled. local data: $(du -sh ~/kalshi-data/raw | cut -f1)"
