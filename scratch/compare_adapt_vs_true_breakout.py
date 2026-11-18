import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from scratch.test_adaptive_regime import AdaptiveDualRegimeEngine
from scratch.test_true_breakout import TrueBreakoutAntiChopEngine
from backend.replay_engine import TOTAL_DAY_SECONDS

eng_adapt = AdaptiveDualRegimeEngine()
eng_tb = TrueBreakoutAntiChopEngine()

print(f"{'Date':<10} | {'Adapt PnL':>12} | {'TrueBreakout PnL':>16} | {'Diff (TB - Adapt)':>18}")
print("=" * 65)

month_stats = {}

for d in eng_adapt.sorted_dates:
    m = d[:7]
    if m not in month_stats:
        month_stats[m] = {"adapt": 0.0, "tb": 0.0}

    eng_adapt.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng_adapt.advance_seconds(5)
    pa = eng_adapt.get_state()['wallet']['realizedPnlInr']

    eng_tb.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng_tb.advance_seconds(5)
    ptb = eng_tb.get_state()['wallet']['realizedPnlInr']

    diff = ptb - pa
    month_stats[m]["adapt"] += pa
    month_stats[m]["tb"] += ptb

    if abs(diff) > 500:
        print(f"{d:<10} | {pa:>12.2f} | {ptb:>16.2f} | {diff:>18.2f}")

print("=" * 65)
print("MONTHLY TOTALS:")
for m in sorted(month_stats.keys()):
    a = month_stats[m]["adapt"]
    t = month_stats[m]["tb"]
    d = t - a
    print(f"{m} -> Adapt: INR {a:>10.2f} | TrueBreakout: INR {t:>10.2f} | Diff: INR {d:>10.2f}")
