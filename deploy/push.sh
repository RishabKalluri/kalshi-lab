#!/usr/bin/env bash
# Run on your laptop: copy code + credentials to the server, then run server_setup.sh there.
#   deploy/push.sh ubuntu@<server-ip>
set -euo pipefail
HOST=${1:?usage: deploy/push.sh user@host}
cd "$(dirname "$0")/.."
rsync -az --delete --exclude .venv --exclude results --exclude __pycache__ --exclude .git --exclude research/data \
  ./ "$HOST:kalshi/"
ssh "$HOST" 'mkdir -p ~/.kalshi && chmod 700 ~/.kalshi'
scp -q ~/.kalshi/kalshi.pem "$HOST:.kalshi/kalshi.pem"
ssh "$HOST" 'chmod 600 ~/.kalshi/kalshi.pem ~/kalshi/.env && sed -i "s|^KALSHI_DATA_ROOT=.*|KALSHI_DATA_ROOT=~/kalshi-data/raw|" ~/kalshi/.env'
ssh "$HOST" "RESTART_ALL=${RESTART_ALL:-0} bash ~/kalshi/deploy/server_setup.sh"
