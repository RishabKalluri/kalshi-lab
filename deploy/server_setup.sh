#!/usr/bin/env bash
# Run ON the server (Ubuntu 24.04, e.g. AWS EC2 t4g.small or t3.small in us-east-1), once:
#   bash ~/kalshi/deploy/server_setup.sh
# Installs uv + chrony (accurate clock for latency/ordering), creates the venv, and installs
# systemd services that restart on failure and start on boot.
set -euo pipefail
cd "$(dirname "$0")/.."
sudo apt-get update -qq
sudo apt-get install -y -qq chrony rsync tmux
sudo systemctl enable --now chrony
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv sync -q
mkdir -p ~/kalshi-data/logs ~/.kalshi
chmod 700 ~/.kalshi
[ -f ~/.kalshi/kalshi.pem ] || echo "!! copy your key to ~/.kalshi/kalshi.pem (deploy/push.sh does this)"
[ -f .env ] || echo "!! .env missing (deploy/push.sh copies it)"

UV="$HOME/.local/bin/uv"
unit() {  # name, description, command, [nice: -5 latency-sensitive .. 15 background]
  local NICE=${4:-0}
  sudo tee /etc/systemd/system/$1.service >/dev/null <<UNIT
[Unit]
Description=$2
After=network-online.target
Wants=network-online.target

[Service]
User=$USER
WorkingDirectory=$PWD
ExecStart=$3
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1
Nice=$NICE
StandardOutput=append:$HOME/kalshi-data/logs/$1.log
StandardError=append:$HOME/kalshi-data/logs/$1.log

[Install]
WantedBy=multi-user.target
UNIT
}
# Priorities: recorder + paper traders first (data and reaction time), dashboard normal,
# backtests/backfills last so they only use spare CPU on this 2-vCPU box.
unit kalshi-recorder "Kalshi market + spot recorder" "$UV run kalshi-lab record" -5   # series come from recorder/config.py MARKETS
# Paper trading: one template unit, one instance per deploy/paper/<id>.json (kalshi-lab paper-start <id>).
# Each run writes a new timestamped results dir, so a restart never overwrites history.
sudo tee /etc/systemd/system/kalshi-paper@.service >/dev/null <<UNIT
[Unit]
Description=Kalshi paper trading: %i
After=network-online.target
Wants=network-online.target

[Service]
User=$USER
WorkingDirectory=$PWD
ExecStart=$UV run kalshi-lab paper-conf %i
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1
Nice=-5
StandardOutput=append:$HOME/kalshi-data/logs/paper-%i.log
StandardError=append:$HOME/kalshi-data/logs/paper-%i.log

[Install]
WantedBy=multi-user.target
UNIT
# migrate from the old per-strategy units
for old in kalshi-paper-gold kalshi-paper-eth; do
  if [ -f /etc/systemd/system/$old.service ]; then
    sudo systemctl disable --now $old 2>/dev/null; sudo rm -f /etc/systemd/system/$old.service
  fi
done
unit kalshi-worker "kalshi-lab background validation worker" "env KALSHI_TEST_WORKERS=1 $UV run kalshi-lab worker" 15

# Daily backfill (idempotent: skips days/markets already on disk) keeps the history growing.
sudo tee /etc/systemd/system/kalshi-backfill.service >/dev/null <<UNIT
[Unit]
Description=kalshi-lab daily backfill
[Service]
Type=oneshot
Nice=15
User=$USER
WorkingDirectory=$PWD
ExecStart=$UV run kalshi-lab backfill --series KXBTC15M KXETH15M KXGOLD15M --days 3
StandardOutput=append:$HOME/kalshi-data/logs/kalshi-backfill.log
StandardError=append:$HOME/kalshi-data/logs/kalshi-backfill.log
UNIT
sudo tee /etc/systemd/system/kalshi-backfill.timer >/dev/null <<UNIT
[Unit]
Description=run kalshi-lab backfill daily
[Timer]
OnCalendar=*-*-* 00:30:00 UTC
Persistent=true
[Install]
WantedBy=timers.target
UNIT
# Dashboard listens on localhost only; reach it with: ssh -L 8501:localhost:8501 <server>
unit kalshi-dashboard "kalshi-lab dashboard" "$UV run streamlit run src/kalshi_lab/dashboard/app.py --server.port 8501 --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false"
sudo systemctl daemon-reload
SERVICES="kalshi-recorder kalshi-worker kalshi-dashboard"
sudo systemctl daemon-reload
sudo systemctl enable --now $SERVICES kalshi-backfill.timer
for f in deploy/paper/*.json; do
  [ -e "$f" ] && sudo systemctl enable --now "kalshi-paper@$(basename "$f" .json)"
done
# Re-deploys restart only stateless services. Restarting the recorder leaves a gap, and restarting
# paper traders resets their state: do that deliberately with RESTART_ALL=1 deploy/push.sh <host>.
if [ "${RESTART_ALL:-0}" = 1 ]; then sudo systemctl restart $SERVICES; else sudo systemctl restart kalshi-worker kalshi-dashboard; fi
sleep 5
systemctl --no-pager --lines=0 status $SERVICES 'kalshi-paper@*' | grep -E "●|Active"
chronyc tracking | grep -E "System time|Last offset"
echo "done. logs: ~/kalshi-data/logs/   dashboard: ssh -L 8501:localhost:8501 <server>, then http://localhost:8501"
