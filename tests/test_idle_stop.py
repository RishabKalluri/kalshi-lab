import shlex
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("unit", "state", "stops"),
    [
        ("kalshi-nightly.service", "activating", False),
        ("kalshi-data-pull.service", "activating", False),
        ("kalshi-data-extra.service", "active", False),
        ("kalshi-nightly.service", "inactive", True),
    ],
)
def test_idle_stop_waits_for_data_services(tmp_path, unit, state, stops):
    idle_since = tmp_path / "idle-since"
    idle_since.write_text("1\n")
    script = (Path(__file__).resolve().parents[1] / "deploy/research/idle-stop.sh").read_text()
    original_state = "STATE=/tmp/idle-since"
    assert original_state in script
    script = script.replace(original_state, f"STATE={shlex.quote(str(idle_since))}")
    stubs = f"""
tmux() {{ return 1; }}
pgrep() {{ return 1; }}
ls() {{ return 1; }}
who() {{ :; }}
date() {{ echo 2000; }}
logger() {{ :; }}
sudo() {{ echo "$*"; }}
systemctl() {{
  if [[ $1 == list-units && " $* " == *" --state="* ]]; then
    for arg; do
      [[ $arg == --state=* ]] && states=${{arg#--state=}}
      if [[ {unit} == $arg ]]; then
        [[ ,$states, == *,{state},* ]] && echo {unit}
        return 0
      fi
    done
  fi
  return 1
}}
"""
    result = subprocess.run(["bash"], input=stubs + script, text=True, capture_output=True, check=True)
    assert result.stdout.strip() == ("shutdown -h now" if stops else "")
    assert not idle_since.exists()
