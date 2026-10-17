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
# Weather and sports books (market-making research) in their own processes, so adding them never restarts the
# crypto recorder.
unit kalshi-recorder-weather "Kalshi weather market recorder" "$UV run kalshi-lab record --group weather" 5
unit kalshi-recorder-sports "Kalshi sports market recorder" "$UV run kalshi-lab record --group sports" 5
unit kalshi-recorder-alts "Kalshi alt-coin 15M recorder (XRP)" "$UV run kalshi-lab record --group alts" -5
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
# Tests no longer run here: this server keeps only 2 days of recorded books (the rest is in S3, storage.py).
if [ -f /etc/systemd/system/kalshi-worker.service ]; then
  sudo systemctl disable --now kalshi-worker 2>/dev/null; sudo rm -f /etc/systemd/system/kalshi-worker.service
fi

# The nightly downloads moved to the research server (deploy/research/setup.sh), which this server wakes at 00:20 UTC.
if [ -f /etc/systemd/system/kalshi-backfill.timer ]; then
  sudo systemctl disable --now kalshi-backfill.timer 2>/dev/null
  sudo rm -f /etc/systemd/system/kalshi-backfill.{timer,service}
fi
sudo tee /etc/systemd/system/kalshi-wake-research.service >/dev/null <<UNIT
[Unit]
Description=start the research server for its nightly downloads
[Service]
Type=oneshot
User=$USER
Environment=PATH=$HOME/.local/bin:/usr/bin:/bin
ExecStart=/bin/sh -c 'aws ec2 start-instances --instance-ids \$\$(aws ec2 describe-instances --filters Name=tag:Name,Values=kalshi-research --query "Reservations[0].Instances[0].InstanceId" --output text)'
StandardOutput=append:$HOME/kalshi-data/logs/wake-research.log
StandardError=append:$HOME/kalshi-data/logs/wake-research.log
UNIT
sudo tee /etc/systemd/system/kalshi-wake-research.timer >/dev/null <<UNIT
[Unit]
Description=wake the research server nightly
[Timer]
OnCalendar=*-*-* 00:20:00 UTC
[Install]
WantedBy=timers.target
UNIT
# The research server's worker pushes results into ~/lab-inbox with a key that can write nothing else (rrsync);
# research-merge copies them into this repo for the dashboard, never touching paper/live strategies or results.
mkdir -p ~/lab-inbox/results ~/lab-inbox/strategies ~/.ssh  # rsync creates no parent folders
KEY="command=\"/usr/bin/rrsync -wo $HOME/lab-inbox\",restrict $(cat deploy/research/worker.pub)"
grep -qF "$(cut -d' ' -f2 deploy/research/worker.pub)" ~/.ssh/authorized_keys 2>/dev/null || echo "$KEY" >> ~/.ssh/authorized_keys
sudo tee /etc/systemd/system/kalshi-research-merge.service >/dev/null <<UNIT
[Unit]
Description=kalshi-lab: merge the research server's results into this repo
[Service]
Type=oneshot
Nice=10
User=$USER
WorkingDirectory=$PWD
ExecStart=$UV run -q kalshi-lab research-merge
UNIT
sudo tee /etc/systemd/system/kalshi-research-merge.timer >/dev/null <<UNIT
[Unit]
Description=merge research results every 2 minutes
[Timer]
OnBootSec=2min
OnUnitActiveSec=2min
[Install]
WantedBy=timers.target
UNIT
# Hourly upload of everything to S3, then delete local recordings older than the keep windows that S3 has
# (storage.py). Needs ~/.aws/credentials for the kalshi-uploader IAM user (write-only to the bucket, no deletes).
uv tool install -q awscli
sudo tee /etc/systemd/system/kalshi-s3.service >/dev/null <<UNIT
[Unit]
Description=kalshi-lab upload data to S3 + trim old local recordings
[Service]
Type=oneshot
Nice=15
IOSchedulingClass=idle
User=$USER
WorkingDirectory=$PWD
Environment=PATH=$HOME/.local/bin:/usr/bin:/bin
ExecStart=-$UV run -q kalshi-lab models-pull
ExecStart=$UV run -q kalshi-lab s3-push
StandardOutput=append:$HOME/kalshi-data/logs/kalshi-s3.log
StandardError=append:$HOME/kalshi-data/logs/kalshi-s3.log
UNIT
sudo tee /etc/systemd/system/kalshi-s3.timer >/dev/null <<UNIT
[Unit]
Description=upload data to S3 hourly
[Timer]
OnCalendar=*-*-* *:05:00 UTC
Persistent=true
[Install]
WantedBy=timers.target
UNIT
# Health check every 2 minutes: writes ~/kalshi-data/health.json (dashboard banner; laptop notifications via
# `kalshi-lab health-watch`). Catches silent failures like a revoked Kalshi API key.
sudo tee /etc/systemd/system/kalshi-health.service >/dev/null <<UNIT
[Unit]
Description=kalshi-lab health check
[Service]
Type=oneshot
Nice=10
User=$USER
WorkingDirectory=$PWD
ExecStart=$UV run -q kalshi-lab health --write
UNIT
sudo tee /etc/systemd/system/kalshi-health.timer >/dev/null <<UNIT
[Unit]
Description=run kalshi-lab health every 2 minutes
[Timer]
OnBootSec=2min
OnUnitActiveSec=2min
[Install]
WantedBy=timers.target
UNIT
# Dashboard listens on localhost only; reach it with: ssh -L 8501:localhost:8501 <server>
unit kalshi-dashboard "kalshi-lab dashboard" "$UV run streamlit run src/kalshi_lab/dashboard/app.py --server.port 8501 --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false"
sudo systemctl daemon-reload
SERVICES="kalshi-recorder kalshi-dashboard"
sudo systemctl daemon-reload
sudo systemctl enable --now $SERVICES kalshi-recorder-weather kalshi-recorder-sports kalshi-recorder-alts kalshi-health.timer kalshi-s3.timer kalshi-wake-research.timer kalshi-research-merge.timer
for f in deploy/paper/*.json; do
  [ -e "$f" ] && sudo systemctl enable --now "kalshi-paper@$(basename "$f" .json)"
done
# Re-deploys restart only stateless services. Restarting the recorder leaves a gap, and restarting
# paper traders resets their state: do that deliberately with RESTART_ALL=1 deploy/push.sh <host>.
if [ "${RESTART_ALL:-0}" = 1 ]; then sudo systemctl restart $SERVICES; else sudo systemctl restart kalshi-dashboard; fi
sleep 5
systemctl --no-pager --lines=0 status $SERVICES 'kalshi-paper@*' | grep -E "●|Active"
chronyc tracking | grep -E "System time|Last offset"
echo "done. logs: ~/kalshi-data/logs/   dashboard: ssh -L 8501:localhost:8501 <server>, then http://localhost:8501"
