import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from scratch.test_adaptive_regime import AdaptiveDualRegimeEngine
from scratch.test_ultimate_confluence_engine import UltimateBreakthroughEngine
from backend.replay_engine import TOTAL_DAY_SECONDS

dates_oct = [f"2026-10-{d:02d}" for d in range(1, 32)]

eng_adapt = AdaptiveDualRegimeEngine()
eng_ult = UltimateBreakthroughEngine()

pnl_adapt = {}
pnl_ult = {}

for d in eng_adapt.sorted_dates:
    if not d.startswith("2026-10"): continue
    
    # Run Adapt
    eng_adapt.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng_adapt.advance_seconds(5)
    st = eng_adapt.get_state()
    pnl_adapt[d] = st['wallet']['realizedPnlInr']

    # Run Ult
    eng_ult.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng_ult.advance_seconds(5)
    st2 = eng_ult.get_state()
    pnl_ult[d] = st2['wallet']['realizedPnlInr']

print(f"{'Date':<12} | {'Adapt (High PnL)':<18} | {'Ult (Lower PnL)':<18} | {'Diff':<12}")
print("=" * 65)
for d in sorted(pnl_adapt.keys()):
    a = pnl_adapt[d]
    u = pnl_ult[d]
    diff = a - u
    print(f"{d:<12} | INR {a:>12,.2f} | INR {u:>12,.2f} | INR {diff:>10,.2f}")

print("=" * 65)
print(f"Total Adapt Oct: INR {sum(pnl_adapt.values()):,.2f}")
print(f"Total Ult Oct:   INR {sum(pnl_ult.values()):,.2f}")
