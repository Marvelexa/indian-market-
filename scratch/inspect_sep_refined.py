import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from scratch.test_refined_60day import OptimizedReplayEngine
from backend.replay_engine import TOTAL_DAY_SECONDS

eng = OptimizedReplayEngine()
sep_dates = [d for d in eng.sorted_dates if d.startswith("2026-09")]

pnl_by_date = {}
trades_by_type = {"OPTION_SEAT": 0, "TREND_SEAT": 0, "CHOP_SEAT": 0}
pnl_by_type = {"OPTION_SEAT": 0.0, "TREND_SEAT": 0.0, "CHOP_SEAT": 0.0}

for d in sep_dates:
    eng.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    st = eng.get_state()
    pnl_by_date[d] = st['wallet']['realizedPnlInr']
    for t in eng.closed_ledger:
        b = t.get('seatBucket', 'OTHER')
        p = t.get('netPnlInr', t.get('pnlInr', 0.0))
        trades_by_type[b] = trades_by_type.get(b, 0) + 1
        pnl_by_type[b] = pnl_by_type.get(b, 0.0) + p

print("=" * 60)
print("September Performance in OptimizedReplayEngine:")
print("=" * 60)
for b in trades_by_type:
    print(f"Bucket {b:<15}: {trades_by_type[b]:>3} trades | PnL: INR {pnl_by_type[b]:>10,.2f}")
print("=" * 60)
print(f"Total September PnL: INR {sum(pnl_by_date.values()):,.2f}")
