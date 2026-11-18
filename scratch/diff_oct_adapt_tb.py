import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from scratch.test_adaptive_regime import AdaptiveDualRegimeEngine
from scratch.test_true_breakout import TrueBreakoutAntiChopEngine
from backend.replay_engine import TOTAL_DAY_SECONDS

eng_adapt = AdaptiveDualRegimeEngine()
eng_tb = TrueBreakoutAntiChopEngine()

print(f"{'Date':<10} | {'Adapt':>10} | {'TrueBreakout':>12} | {'Diff':>10}")
print("=" * 50)
for d in eng_adapt.sorted_dates:
    if not d.startswith("2026-10"): continue
    eng_adapt.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5): eng_adapt.advance_seconds(5)
    pa = eng_adapt.get_state()['wallet']['realizedPnlInr']

    eng_tb.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5): eng_tb.advance_seconds(5)
    ptb = eng_tb.get_state()['wallet']['realizedPnlInr']

    print(f"{d:<10} | {pa:>10.2f} | {ptb:>12.2f} | {ptb - pa:>10.2f}")
