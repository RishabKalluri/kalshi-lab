"""uv run python research/fit_vol_model.py KXETH15M [--until 2026-09-14T02:07] [--pct 0.7]"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "strategies"))
from vol_fit import PARAMS, fit_model  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("series")
ap.add_argument("--until")
ap.add_argument("--pct", type=float, default=0.7)
a = ap.parse_args()
name = fit_model(a.series, a.until, a.pct)
m = json.loads((PARAMS / name).read_text())
print(f"saved {name}: threshold {m['ratio_threshold']:.3f} from {m['n_markets']} markets")
