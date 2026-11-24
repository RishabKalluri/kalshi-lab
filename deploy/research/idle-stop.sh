#!/usr/bin/env bash
# Stop this EC2 instance (shutdown = stop, not terminate) after 30 idle minutes: no agents (Claude processes or
# agent/head tmux sessions), no test jobs queued or running, no data job running, nobody logged in over SSH.
# Runs every 5 minutes from a systemd timer.
STATE=/tmp/idle-since
busy=""
tmux ls 2>/dev/null | grep -qE "^(agent|head)" && busy="agents"
pgrep -u agent >/dev/null && busy="$busy agent-user"
# (one ls per folder: `ls a/*.json b/*.json` fails when either glob is empty, which read running jobs as idle)
for q in running queue; do ls /srv/kalshi/results/_jobs/$q/*.json >/dev/null 2>&1 && busy="$busy tests-$q"; done
# Oneshot downloads are activating while running, including the persistent nightly catch-up.
systemctl list-units --type=service --state=active,activating,reloading --no-legend \
  kalshi-nightly.service 'kalshi-data-*.service' | grep -q . && busy="$busy data-jobs"
[ -n "$(who)" ] && busy="$busy ssh"
# If a scheduled batch or download starts within 45 min: stay up.
for t in kalshi-nightly kalshi-agents; do
  nxt=$(systemctl show $t.timer -p NextElapseUSecRealtime --value 2>/dev/null)
  [ -n "$nxt" ] && [ $(( $(date -d "$nxt" +%s 2>/dev/null || echo 0) - $(date +%s) )) -lt 2700 ] \
    && [ $(( $(date -d "$nxt" +%s 2>/dev/null || echo 0) - $(date +%s) )) -gt 0 ] && busy="$busy $t-soon"
done
if [ -n "$busy" ]; then rm -f $STATE; exit 0; fi
[ -f $STATE ] || date +%s > $STATE
if [ $(( $(date +%s) - $(cat $STATE) )) -ge 1800 ]; then
  logger "idle-stop: idle 30 min, stopping instance"; rm -f $STATE; sudo shutdown -h now
fi
