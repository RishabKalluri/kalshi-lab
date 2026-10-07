#!/usr/bin/env bash
# Make http://localhost:8501 on this laptop show the SERVER's dashboard, via an SSH tunnel that
# reconnects by itself (after sleep, wifi changes, server restarts). Safe to run repeatedly.
#   deploy/dashboard.sh [host]
HOST=${1:-kalshi}
if ! tmux has-session -t kalshi-tunnel 2>/dev/null; then
  tmux new-session -d -s kalshi-tunnel "while true; do ssh -N -o ServerAliveInterval=15 -o ServerAliveCountMax=2 -o ExitOnForwardFailure=yes -L 8501:localhost:8501 $HOST; sleep 3; done"
  sleep 3
fi
# Laptop notifications when the server's health check reports a problem (kalshi-lab health-watch).
if ! tmux has-session -t kalshi-health 2>/dev/null; then
  tmux new-session -d -s kalshi-health -c "$(dirname "$0")/.." "uv run kalshi-lab health-watch --host $HOST >> ~/kalshi-data/logs/health-watch.log 2>&1"
fi
open http://localhost:8501
echo "server dashboard: http://localhost:8501 (tunnel runs in tmux session kalshi-tunnel)"
