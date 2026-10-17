# Macro-release windows + holidays (research only)
Agent run 20261017-0101-2, brief "KXSOL15M: your choice of idea". Screens in research/ (dev data only, before 2026-09-01).

## H1: scheduled macro releases as vol bells (all 5 coins)
Hypothesis: us-hours-vol found the 9:30 ET bell underpriced, and the whole-8:30 slot looked priced correctly only because most days have no release,
so event days could be underpriced. Calendar from bls.gov monthly schedules (CPI, Employment Situation, PPI: 25 dates Jan-Aug) and FOMC 14:00 (5 decisions).
Result (`research/screen.py`): 8:30 event windows: median realized/implied vol 0.98 (control days 1.02), realized vs trailing 15m vol 0.97x (control 1.12x):
no vol step in crypto at releases. Underdog (10-45c) at h=840: 0.0c (n=56, se 5.7) vs control +0.9c. FOMC: 13 markets, too few; ratio 1.08 vs 0.95, underdog +7.8c (se 10.8) at h=840, -22c at h=720. Rejected.

## H2: US market holidays / weekends on SOL
Holiday weekdays: realized/implied vol equals ordinary weekdays on all 5 coins (SOL 1.062 vs 1.063). SOL weekend ratio is 1.15 (Kalshi underprices SOL weekend vol ~8%),
but buying the underdog still loses 3-4c at every horizon on weekends (`research/solwk.py`, n=800-3400 per cell), only the 80-97c weekend favourite is +1.1c (known, capacity-limited). Rejected.

Status: rejected (research).
