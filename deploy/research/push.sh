#!/usr/bin/env bash
# Laptop: deploy code to the research server (/srv/kalshi) and run setup.sh there. Agents' work lives on the research
# server, so strategies/ (except _template and _budgets.json) and results/ are copied only on the first deploy.
#   deploy/research/push.sh          (the server must be running: deploy/research.sh start)
set -euo pipefail
cd "$(dirname "$0")/../.."
H=kalshi-research
ssh $H 'sudo mkdir -p /srv/kalshi && sudo chown ubuntu /srv/kalshi'
FIRST=$(ssh $H '[ -d /srv/kalshi/strategies ] && echo 0 || echo 1')
EXC=(--exclude .venv --exclude __pycache__ --exclude research/data --exclude .env --exclude '*.pem' --exclude /results)
[ "$FIRST" = 1 ] || EXC=(--include /strategies/_template/*** --include /strategies/_budgets.json --exclude '/strategies/*' "${EXC[@]}")
rsync -az --delete "${EXC[@]}" ./ $H:/srv/kalshi/
if [ "$FIRST" = 1 ]; then  # the test history (ledger, jobs, run outputs); paper/live results stay on the trading server
  rsync -az --exclude '/paper-*' --exclude '/live-*' results/ $H:/srv/kalshi/results/
fi
ssh $H 'bash /srv/kalshi/deploy/research/setup.sh'
