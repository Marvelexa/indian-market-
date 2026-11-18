import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from scratch.test_ultimate_confluence_engine import UltimateBreakthroughEngine
from backend.replay_engine import TOTAL_DAY_SECONDS

eng = UltimateBreakthroughEngine()
eng.set_date("2026-10-23", auto_play=True)
for _ in range(TOTAL_DAY_SECONDS // 5):
    eng.advance_seconds(5)

st = eng.get_state()
w = st['wallet']
print(f"\n=== INSPECTING 2026-10-23 in UltimateBreakthroughEngine ===")
print(f"PnL: INR {w['realizedPnlInr']:,.2f} | Trades: {w['totalTrades']} | Wins: {w['wins']}")
for t in eng.closed_ledger:
    print(f"  {t['symbol']:<10} | Side: {t['side']:<4} | Type: {t.get('seatBucket',''):<25} | Reason: {t.get('exitReason',''):<20} | PnL: INR {t.get('netPnlInr', t.get('pnlInr',0)):>8,.2f}")
