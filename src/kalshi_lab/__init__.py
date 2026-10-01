import importlib
import sys

COMMANDS = {
    "record": ("kalshi_lab.recorder.main", "main"),
    "backfill": ("kalshi_lab.data.backfill", "main"),
    "backtest": ("kalshi_lab.backtest", "main"),
    "paper": ("kalshi_lab.live.run", "paper"),
    "live": ("kalshi_lab.live.run", "live"),
    "dashboard": ("kalshi_lab.dashboard.launch", "main"),
    "test": ("kalshi_lab.remote", "test"),          # laptop: sync + smoke on server + queue quick/full
    "jobs": ("kalshi_lab.remote", "jobs"),          # list background jobs (runs on the server)
    "validate": ("kalshi_lab.validate", "main"),    # server: run one stage
    "enqueue": ("kalshi_lab.jobs", "enqueue"),      # server: queue stages
    "jobs-local": ("kalshi_lab.jobs", "list_jobs"),
    "worker": ("kalshi_lab.jobs", "worker"),        # server: background job loop (systemd)
    "cancel": ("kalshi_lab.jobs", "cancel"),        # server: cancel a queued/running job
    "new": ("kalshi_lab.strategy_dir", "new"),          # create strategies/<slug>/ from the template
    "data": ("kalshi_lab.validate", "data_status"),
    "audit": ("kalshi_lab.validate", "audit"),          # independent re-run vs the ledger (before live)     # what history exists; dev vs lockbox split
    "pull": ("kalshi_lab.remote", "pull"),              # copy the server's data for a series to this laptop
    "paper-start": ("kalshi_lab.paper_ctl", "start"),  # laptop: paper trade a registry strategy on the server
    "paper-stop": ("kalshi_lab.paper_ctl", "stop"),
    "paper-list": ("kalshi_lab.paper_ctl", "list_"),
    "paper-conf": ("kalshi_lab.paper_ctl", "conf"),    # server: run deploy/paper/<id>.json (systemd template)
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"usage: kalshi-lab {{{','.join(COMMANDS)}}} [args]   (-h on any command for help)")
        sys.exit(1)
    mod, fn = COMMANDS[sys.argv[1]]
    getattr(importlib.import_module(mod), fn)(sys.argv[2:])
