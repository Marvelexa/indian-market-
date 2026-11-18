import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from scratch.test_adaptive_regime import AdaptiveDualRegimeEngine
from backend.replay_engine import TOTAL_DAY_SECONDS

eng = AdaptiveDualRegimeEngine()
sep_dates = [d for d in eng.sorted_dates if d.startswith("2026-09")]

print("=== SEPTEMBER DAY BY DAY IN AdaptiveDualRegimeEngine ===")
for d in sep_dates:
    eng.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    st = eng.get_state()
    w = st['wallet']
    pnl = w['realizedPnlInr']
    t = w['totalTrades']
    wn = w['wins']
    ls = t - wn
    print(f"{d} | PnL: INR {pnl:>9,.2f} | Trades: {t:>2} (W: {wn:>2}, L: {ls:>2})")
