#!/usr/bin/env bash
# Run on your laptop: download all data from S3 (storage.py) + the server's results for local backtests/dashboard.
#   deploy/pull_data.sh
set -euo pipefail
cd "$(dirname "$0")/.."
B=s3://${KALSHI_S3_BUCKET:-kalshi-data-531080694882}
aws s3 sync --only-show-errors --size-only "$B/raw/" ~/kalshi-data/raw/
aws s3 sync --only-show-errors --size-only "$B/backfill/" ~/kalshi-data/backfill/
rsync -az kalshi:kalshi/results/ results/
echo "pulled. local data: $(du -sh ~/kalshi-data | cut -f1)"
