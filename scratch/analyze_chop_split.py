import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from scratch.test_adaptive_regime import AdaptiveDualRegimeEngine
from backend.replay_engine import TOTAL_DAY_SECONDS, INDEX_SET

eng = AdaptiveDualRegimeEngine()
sep_aug_dates = [d for d in eng.sorted_dates if d.startswith("2026-08") or d.startswith("2026-09")]

index_chop_pnl = 0.0
equity_chop_pnl = 0.0
trend_pnl = 0.0

index_chop_trades = 0
equity_chop_trades = 0
trend_trades = 0

for d in sep_aug_dates:
    eng.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    
    for t in eng.closed_ledger:
        p = t.get('netPnlInr', t.get('pnlInr', 0.0))
        is_idx = t['symbol'] in INDEX_SET
        is_chop = t.get('seatBucket') == "CHOP_PING_PONG_SEAT"
        if is_chop:
            if is_idx:
                index_chop_pnl += p
                index_chop_trades += 1
            else:
                equity_chop_pnl += p
                equity_chop_trades += 1
        else:
            trend_pnl += p
            trend_trades += 1

print("=" * 70)
print(f"August & September Breakdown in AdaptiveDualRegimeEngine:")
print("=" * 70)
print(f"Trend Trades:       {trend_trades:>3} trades | PnL: INR {trend_pnl:>10,.2f}")
print(f"Equity Chop Trades: {equity_chop_trades:>3} trades | PnL: INR {equity_chop_pnl:>10,.2f}")
print(f"Index Chop Trades:  {index_chop_trades:>3} trades | PnL: INR {index_chop_pnl:>10,.2f}")
print("=" * 70)
print(f"Net Total PnL: INR {trend_pnl + equity_chop_pnl + index_chop_pnl:,.2f}")
