import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from scratch.test_adaptive_regime import AdaptiveDualRegimeEngine
from backend.replay_engine import TOTAL_DAY_SECONDS, INDEX_SET

eng = AdaptiveDualRegimeEngine()
oct_dates = [d for d in eng.sorted_dates if d.startswith("2026-10")]

trend_pnl = 0.0
trend_trades = 0
chop_pnl = 0.0
chop_trades = 0

for d in oct_dates:
    eng.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    for t in eng.closed_ledger:
        p = t.get('netPnlInr', t.get('pnlInr', 0.0))
        if t.get('seatBucket') == "CHOP_PING_PONG_SEAT":
            chop_pnl += p
            chop_trades += 1
        else:
            trend_pnl += p
            trend_trades += 1

print(f"October Trend Trades: {trend_trades} | PnL: INR {trend_pnl:,.2f}")
print(f"October Chop Trades:  {chop_trades} | PnL: INR {chop_pnl:,.2f}")
print(f"October Total PnL:    INR {trend_pnl + chop_pnl:,.2f}")
