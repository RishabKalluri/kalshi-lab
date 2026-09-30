#!/bin/zsh
# Keeps the recorder running; restarts it if it exits. To pick up code changes without
# stopping the loop:  pkill -TERM -f "kalshi-lab record"
cd "$(dirname "$0")/.."
mkdir -p ~/kalshi-data/logs
# Keep the Mac awake (idle/system/disk sleep) for as long as this script runs.
# Closing the lid on battery still sleeps the machine.
caffeinate -ims -w $$ &
while true; do
  uv run kalshi-lab record --series ${=SERIES:-KXBTC15M KXETH15M KXGOLD15M} >> ~/kalshi-data/logs/recorder.log 2>&1
  echo "$(date '+%F %T') recorder exited ($?), restarting in 2s" >> ~/kalshi-data/logs/recorder.log
  sleep 2
done
