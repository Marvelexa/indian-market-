import sys
sys.path.insert(0, '.')
from backend.replay_engine import IndianPastDateReplayEngine

engine = IndianPastDateReplayEngine.get_instance()
engine.set_date('2026-11-04', auto_play=False, speed=1)

for sec in range(0, 22500, 10):
    engine.advance_seconds(10)

st = engine.get_state()
w = st['wallet']
print('=== 2026-11-04 RESULT WITH TP 1/2/3/LAST LADDER & 1500 CAP ===')
print('Total Trades:', w['totalTrades'], 'Wins:', w['wins'], 'Losses:', w['losses'], 'Win Rate:', f"{w['winRatePct']}%")
print('Realized PnL: INR', w['realizedPnlInr'])
print('TP 1 Hits:', w['tp1Hits'], 'TP 2 Hits:', w['tp2Hits'], 'TP 3/LAST Hits:', w['tp3Hits'] + w['tpLastHits'], 'SL Hits:', w['slHits'], 'Max Loss Hits:', w['maxLossCapHits'])
print('--- CLOSED TRADES ---')
for t in engine.closed_ledger:
    print(f"{t['exitTimeFormatted']} | {t['symbol']} | {t['side']} | ₹{t['entryPrice']} -> ₹{t['exitPrice']} | PnL: ₹{t['netPnlInr']} | {t['exitReason']}")
