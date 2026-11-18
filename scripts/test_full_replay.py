import sys
sys.path.insert(0, r"d:\new start")
import datetime
from backend.replay_engine import IndianPastDateReplayEngine, WHITELIST_14_SYMBOLS, TOTAL_DAY_SECONDS

engine = IndianPastDateReplayEngine.get_instance()
engine.set_date("2026-11-16", auto_play=True, speed=300)

print(f"Testing replay on {engine.current_date}...")
while engine.second_of_day < TOTAL_DAY_SECONDS and engine.is_running:
    engine.advance_seconds(300)

print(f"\nTotal Closed Trades: {len(engine.closed_ledger)}")
print(f"Realized PnL: ₹{engine.realized_pnl_inr:,.2f}")
print("\nTrades:")
for t in reversed(engine.closed_ledger):
    print(f"{t['entryTimeFormatted']:<9} {t['symbol']:<12} {t['side']:<5} {t['seatBucket']:<28} PnL: ₹{t['netPnlInr']:<10.2f} {t['exitReason']}")
