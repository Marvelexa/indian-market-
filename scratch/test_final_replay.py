import sys
sys.path.insert(0, '.')
from backend.replay_engine import IndianPastDateReplayEngine

engine = IndianPastDateReplayEngine.get_instance()
engine.set_date('2026-11-04', auto_play=False, speed=1)

for sec in range(0, 22500, 10):
    engine.advance_seconds(10)

st = engine.get_state()
w = st['wallet']
print('=== 2026-11-04 RESULTS WITH INSTITUTIONAL 20K LADDER ===')
print('Total Trades:', w['totalTrades'], 'Wins:', w['wins'], 'Losses:', w['losses'])
print('Realized PnL: INR', w['realizedPnlInr'])
print('\n--- CLOSED TRADES ---')
for t in reversed(engine.closed_ledger):
    print(f"{t['entryTimeFormatted']} -> {t['exitTimeFormatted']} | {t['symbol']} {t['side']} | Entry: {t['entryPrice']} -> {t['exitPrice']} | PnL: ₹{t['netPnlInr']} | Exit: {t['exitReason']}")
