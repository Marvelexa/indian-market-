import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from scratch.test_adaptive_regime import AdaptiveDualRegimeEngine
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS

eng_adapt = AdaptiveDualRegimeEngine()
eng_back = IndianPastDateReplayEngine()

oct_dates = [d for d in eng_adapt.sorted_dates if d.startswith("2026-10")]

print(f"{'Date':<12} | {'Adapt (29.8k)':<15} | {'Backend (21.9k)':<15} | {'Diff':<10}")
print("=" * 60)
for d in oct_dates:
    eng_adapt.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng_adapt.advance_seconds(5)
    st1 = eng_adapt.get_state()
    p1 = st1['wallet']['realizedPnlInr']

    eng_back.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng_back.advance_seconds(5)
    st2 = eng_back.get_state()
    p2 = st2['wallet']['realizedPnlInr']

    print(f"{d:<12} | INR {p1:>10,.2f} | INR {p2:>10,.2f} | INR {p1 - p2:>8,.2f}")
