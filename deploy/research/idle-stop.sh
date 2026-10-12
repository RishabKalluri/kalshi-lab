#!/usr/bin/env bash
# Stop this EC2 instance (shutdown = stop, not terminate) after 30 idle minutes: no agents (Claude processes or
# agent/head tmux sessions), no test jobs queued or running, no data job running, nobody logged in over SSH.
# Runs every 5 minutes from a systemd timer.
STATE=/tmp/idle-since
busy=""
tmux ls 2>/dev/null | grep -qE "^(agent|head)" && busy="agents"
pgrep -u agent >/dev/null && busy="$busy agent-user"
ls /srv/kalshi/results/_jobs/running/*.json /srv/kalshi/results/_jobs/queue/*.json >/dev/null 2>&1 && busy="$busy tests"
for u in kalshi-nightly kalshi-data-pull; do systemctl is-active --quiet $u && busy="$busy $u"; done
[ -n "$(who)" ] && busy="$busy ssh"
if [ -n "$busy" ]; then rm -f $STATE; exit 0; fi
[ -f $STATE ] || date +%s > $STATE
if [ $(( $(date +%s) - $(cat $STATE) )) -ge 1800 ]; then
  logger "idle-stop: idle 30 min, stopping instance"; rm -f $STATE; sudo shutdown -h now
fi
