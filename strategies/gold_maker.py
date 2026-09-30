"""Gold market maker: SpreadMaker with the OKX-gold model gating quotes, tight inventory, and a flatten
before close.

Why gold: KXGOLD15M settles on a single Pyth print, and OKX's XAU perp tracks Pyth to ~$1 over 15 min
(research/gold_robust.py), so a spot model adds information the thinner gold market underweights
late in the window. Taking that edge doesn't survive the spread + taker fee; making does, because
makers pay no fee: the model only decides which side of the touch it's safe to rest on.

Needs a live gold spot feed (recorder: okx:XAU-USDT-SWAP). Parameters were tuned on ~14 hours of
recorded books (see the README), so treat results as a hypothesis until paper trading confirms them.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from maker import SpreadMaker  # noqa: E402


class GoldMaker(SpreadMaker):
    params = {**SpreadMaker.params, "gate": 0, "skew_pos": 5, "flatten": True}
