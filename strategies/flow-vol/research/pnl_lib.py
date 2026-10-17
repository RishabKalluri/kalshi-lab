import numpy as np, pandas as pd
from r2 import fitpred
def wf(d, cols):
    out = pd.Series(np.nan, index=d.index)
    for m in pd.period_range("2026-03", "2026-08", freq="M"):
        s, e = m.start_time.tz_localize("UTC"), (m + 1).start_time.tz_localize("UTC")
        a = d[d.close < s]; b = d[(d.close >= s) & (d.close < e)]
        out[b.index] = fitpred(a, b, cols)
    return out
