import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from scratch.test_hybrid_optimal import HybridOptimalEngine
from scratch.test_refined_60day import OptimizedReplayEngine
from backend.replay_engine import TOTAL_DAY_SECONDS

eng_hyb = HybridOptimalEngine()
eng_ref = OptimizedReplayEngine()

sep_dates = [d for d in eng_hyb.sorted_dates if d.startswith("2026-09")]
print(f"{'Date':<12} | {'Hybrid PnL':<14} | {'Refined PnL':<14} | {'Diff':<12}")
print("=" * 60)
for d in sep_dates:
    eng_hyb.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng_hyb.advance_seconds(5)
    st1 = eng_hyb.get_state()
    p1 = st1['wallet']['realizedPnlInr']

    eng_ref.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng_ref.advance_seconds(5)
    st2 = eng_ref.get_state()
    p2 = st2['wallet']['realizedPnlInr']

    print(f"{d:<12} | INR {p1:>10,.2f} | INR {p2:>10,.2f} | INR {p2 - p1:>8,.2f}")
