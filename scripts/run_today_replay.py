import sys
sys.path.insert(0, r'd:\new start')
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS

engine = IndianPastDateReplayEngine.get_instance()
engine.set_date('2026-11-16', auto_play=True, speed=500)

while engine.second_of_day < TOTAL_DAY_SECONDS:
    engine.advance_seconds(5)

print('=== TODAY REPLAY CLOSED LEDGER (2026-11-16) ===')
print(f'Total Trades: {len(engine.closed_ledger)}')
print(f'Realized PnL: {engine.realized_pnl_inr:+,.2f} INR')
for idx, t in enumerate(engine.closed_ledger):
    print(f"{idx+1:<2} {t.get('entryTime', '')} -> {t.get('exitTime', '')} | {t.get('symbol', ''):<10} {t.get('side', ''):<4} | Net: {t.get('netPnlInr', 0.0):+9.2f} INR | {t.get('exitReason', '')}")
