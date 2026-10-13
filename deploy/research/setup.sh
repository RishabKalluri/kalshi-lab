#!/usr/bin/env bash
# Research server (EC2 kalshi-research, Ubuntu 24.04 arm64) setup; idempotent. Run by deploy/research/push.sh.
#
# Who can do what (file permissions and a sandbox, not just the agent guard hook):
#   ubuntu      ops: code, data syncs from S3, nightly downloads. Only user with the instance's AWS role.
#   worker      runs test jobs (kalshi-worker service); the only writer of the ledger; may sudo kalshi-sandbox.
#   agent       Claude strategy agents: reads code + development data + ledger; writes strategies/, IDEAS.md, the
#               job queue. Can't read lockbox-dated data, the lockbox token or other users' homes.
#   runner      dev stages of agents' code (sandbox): development data only; can't write the ledger or job state.
#   lockrunner  lockbox stage (sandbox): all data; writes only places agents can't read.
# Groups: lab = {ubuntu, worker, agent, runner} (shared strategies/, results/); kdata = {ubuntu, worker, lockrunner}
# (lockbox-dated data, lockbox outputs).
set -euo pipefail
R=/srv/kalshi
D=/srv/kalshi-data
sudo apt-get install -y -qq rsync tmux zstd >/dev/null

# --- users and groups
for g in lab kdata; do getent group $g >/dev/null || sudo groupadd $g; done
for u in worker agent runner lockrunner; do id $u >/dev/null 2>&1 || sudo useradd -m -s /bin/bash $u; done
sudo usermod -aG lab,kdata ubuntu
sudo usermod -aG lab,kdata worker
sudo usermod -aG lab agent
sudo usermod -aG lab runner
sudo usermod -aG kdata lockrunner
sudo chmod 750 /home/worker /home/agent /home/runner /home/lockrunner
# the lockbox token: only lockrunner (inside the lockbox sandbox) has it
if ! sudo test -f /home/lockrunner/.kalshi/lockbox.token; then
  sudo -u lockrunner bash -c 'umask 077; mkdir -p ~/.kalshi; head -c 16 /dev/urandom | od -An -tx1 | tr -d " \n" > ~/.kalshi/lockbox.token'
fi
[ -x /usr/local/bin/uv ] || sudo install -m 755 ~/.local/bin/uv /usr/local/bin/uv
[ -x ~/.local/bin/aws ] || uv tool install -q awscli   # ubuntu only: S3 via the instance role
echo "[safe]
	directory = $R" | sudo tee /etc/gitconfig >/dev/null
sudo tee /etc/profile.d/kalshi.sh >/dev/null <<EOF
export KALSHI_SITE=research KALSHI_DATA_ROOT=$D/raw UV_NO_SYNC=1 PATH=\$HOME/.local/bin:/usr/local/bin:\$PATH
umask 002
EOF

# --- code: owned by ubuntu, readable by all; strategies/ shared (sticky: only a folder's owner can remove it)
cd $R
# Python itself must be readable by every user (uv's default lives in ubuntu's private home)
sudo mkdir -p /opt/uv-python && sudo chown ubuntu /opt/uv-python
export UV_PYTHON_INSTALL_DIR=/opt/uv-python
if ! readlink -f .venv/bin/python | grep -q ^/opt/uv-python; then rm -rf .venv; fi
uv sync -q
sudo chown ubuntu:lab $R && sudo chmod 755 $R
sudo chown ubuntu:lab strategies && sudo chmod 3775 strategies
for f in strategies/*/; do
  s=$(basename "$f")
  [ "${s:0:1}" = _ ] && continue
  st=$(python3 -c "import json;print(json.load(open('$f/config.json')).get('status',''))" 2>/dev/null || true)
  if [ "$st" = paper ] || [ "$st" = live ] || grep -qs "strategies/$s/" deploy/paper/*.json; then
    sudo chown -R ubuntu:lab "$f" && sudo chmod -R go-w "$f"      # trading: agents may read, not change
  else
    sudo chgrp -R lab "$f" && sudo chmod -R g+w "$f" && sudo find "$f" -type d -exec chmod g+s {} +
  fi
done
sudo chgrp lab strategies/IDEAS.md && sudo chmod 664 strategies/IDEAS.md
# research/data: datasets derived from development data (research scripts, fit()); shared by agents and dev runs
mkdir -p research/data && sudo chown ubuntu:lab research/data && sudo chmod 2775 research/data

# --- results: the worker's; agents may queue jobs; lockbox outputs and sandbox scratch kept from agents
sudo mkdir -p results/_ledger results/_jobs/{queue,running,done} results/_sandbox results/_lockbox
sudo chown -R worker:lab results && sudo chmod 2775 results results/_jobs results/_sandbox
sudo chmod 3775 results/_jobs/queue
sudo chown worker:worker results/_ledger && sudo chmod 755 results/_ledger
sudo chown worker:kdata results/_lockbox && sudo chmod 2770 results/_lockbox

# --- the worker pushes results to the trading server's drop folder (its key can write nothing else there)
sudo -u worker bash -c '[ -f ~/.ssh/id_ed25519 ] || { mkdir -p -m 700 ~/.ssh; ssh-keygen -q -t ed25519 -N "" -C kalshi-research-worker -f ~/.ssh/id_ed25519; }
printf "Host kalshi-inbox\n  HostName 3.229.34.35\n  User ubuntu\n  IdentityFile ~/.ssh/id_ed25519\n  StrictHostKeyChecking accept-new\n" > ~/.ssh/config'

# --- data: development files world-readable, lockbox-dated ones group kdata only (storage.py fix_perms)
sudo mkdir -p $D/raw $D/backfill $D/logs
sudo chown ubuntu:kdata $D $D/raw $D/backfill && sudo chmod 2755 $D $D/raw $D/backfill
sudo chown ubuntu:ubuntu $D/logs

# --- sandbox launcher; the worker may run it as root and nothing else
sudo install -o root -g root -m 755 deploy/research/kalshi-sandbox /usr/local/sbin/kalshi-sandbox
echo "worker ALL=(root) NOPASSWD: /usr/local/sbin/kalshi-sandbox" | sudo tee /etc/sudoers.d/kalshi-worker >/dev/null
sudo chmod 440 /etc/sudoers.d/kalshi-worker

# --- only root and ubuntu may reach the instance metadata service (the server's AWS credentials)
sudo tee /etc/systemd/system/kalshi-imds-guard.service >/dev/null <<'UNIT'
[Unit]
Description=only root and ubuntu may reach the EC2 metadata service (AWS credentials)
After=network-pre.target
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c 'iptables -D OUTPUT -d 169.254.169.254 -j KALSHI-IMDS 2>/dev/null; iptables -F KALSHI-IMDS 2>/dev/null || iptables -N KALSHI-IMDS; iptables -A KALSHI-IMDS -m owner --uid-owner 0 -j RETURN; iptables -A KALSHI-IMDS -m owner --uid-owner ubuntu -j RETURN; iptables -A KALSHI-IMDS -j REJECT; iptables -I OUTPUT -d 169.254.169.254 -j KALSHI-IMDS'
[Install]
WantedBy=multi-user.target
UNIT

# --- services
ENV="Environment=KALSHI_SITE=research KALSHI_DATA_ROOT=$D/raw PYTHONUNBUFFERED=1"
sudo tee /etc/systemd/system/kalshi-worker.service >/dev/null <<UNIT
[Unit]
Description=kalshi-lab test worker (runs agents' code only via kalshi-sandbox)
After=network-online.target kalshi-data-pull.service
[Service]
User=worker
WorkingDirectory=$R
$ENV
Environment=KALSHI_SANDBOX=1 KALSHI_PUSH_PREFIX=
UMask=0002
ExecStart=$R/.venv/bin/python -m kalshi_lab worker --push kalshi-inbox
Restart=always
RestartSec=5
StandardOutput=append:$D/logs/worker.log
StandardError=append:$D/logs/worker.log
[Install]
WantedBy=multi-user.target
UNIT
# all data from S3 at boot and hourly (new recordings for the lockbox's recorded-books run)
sudo tee /etc/systemd/system/kalshi-data-pull.service >/dev/null <<UNIT
[Unit]
Description=kalshi-lab: sync data from S3 + set permissions
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=$R
$ENV
Environment=PATH=/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$R/.venv/bin/python -m kalshi_lab s3-pull
StandardOutput=append:$D/logs/data-pull.log
StandardError=append:$D/logs/data-pull.log
UNIT
sudo tee /etc/systemd/system/kalshi-data-pull.timer >/dev/null <<UNIT
[Unit]
Description=sync data from S3 at boot and hourly
[Timer]
OnBootSec=1min
OnCalendar=*-*-* *:20:00 UTC
[Install]
WantedBy=timers.target
UNIT
# nightly downloads (moved here from the trading server, which wakes this server at 00:20 UTC)
sudo tee /etc/systemd/system/kalshi-nightly.service >/dev/null <<UNIT
[Unit]
Description=kalshi-lab nightly downloads -> S3
After=network-online.target
[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=$R
$ENV
Environment=PATH=/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin
UMask=0027
ExecStart=$R/.venv/bin/python -m kalshi_lab s3-pull
ExecStart=$R/.venv/bin/python -m kalshi_lab backfill --series KXBTC15M KXETH15M KXSOL15M KXGOLD15M KXXRP15M KXDOGE15M --days 3
ExecStart=$R/.venv/bin/python -m kalshi_lab s3-push --dirs backfill --no-trim
ExecStart=$R/.venv/bin/python -c "from kalshi_lab.storage import fix_perms; fix_perms()"
StandardOutput=append:$D/logs/nightly.log
StandardError=append:$D/logs/nightly.log
UNIT
sudo tee /etc/systemd/system/kalshi-nightly.timer >/dev/null <<UNIT
[Unit]
Description=nightly downloads
[Timer]
OnCalendar=*-*-* 00:30:00 UTC
Persistent=true
[Install]
WantedBy=timers.target
UNIT

# --- idle auto-stop (counts agents, tests, data jobs and SSH logins as busy)
sudo install -m 755 deploy/research/idle-stop.sh /home/ubuntu/bin/idle-stop.sh

sudo systemctl daemon-reload
sudo systemctl enable --now kalshi-imds-guard.service kalshi-data-pull.timer kalshi-nightly.timer >/dev/null
sudo systemctl enable kalshi-worker >/dev/null
sudo systemctl restart kalshi-imds-guard.service
echo "research setup done"
