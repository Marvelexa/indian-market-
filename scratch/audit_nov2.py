import sys
sys.path.insert(0, '.')
from backend.replay_engine import IndianPastDateReplayEngine

engine = IndianPastDateReplayEngine.get_instance()
engine.set_date('2026-11-02', auto_play=False, speed=1)

# Advance and log status at 1:15 PM (second 14400)
# 09:15 AM to 01:15 PM = 4 hours = 14400 seconds
status_at_115 = None

for sec in range(0, 22500, 10):
    engine.advance_seconds(10)
    if engine.second_of_day == 14400:
        status_at_115 = {
            "realizedPnl": engine.realized_pnl_inr,
            "activePositions": len(engine.active_positions),
            "symbolTrades": dict(engine.symbol_trades_today),
            "closedCount": len(engine.closed_ledger)
        }

st = engine.get_state()
w = st['wallet']
print('=== 2026-11-02 COMPLETE AUDIT ===')
print(f"Total Trades: {w['totalTrades']}, Wins: {w['wins']}, Losses: {w['losses']}")
print(f"Realized PnL: ₹{w['realizedPnlInr']}")
print(f"Circuit Breaker Tripped: {w.get('isCircuitBreakerTripped')}")

print('\n=== STATUS AT 01:15:00 PM IST ===')
if status_at_115:
    print(f"Realized PnL at 1:15 PM: ₹{status_at_115['realizedPnl']}")
    print(f"Active Positions at 1:15 PM: {status_at_115['activePositions']}")
    print(f"Closed Trades by 1:15 PM: {status_at_115['closedCount']}")
    print(f"Symbols Traded: {status_at_115['symbolTrades']}")

print('\n=== ALL TRADES CHRONOLOGICAL ===')
for t in reversed(engine.closed_ledger):
    print(f"{t['entryTimeFormatted']} -> {t['exitTimeFormatted']} | {t['symbol']} {t['side']} | Entry: {t['entryPrice']} -> {t['exitPrice']} | PnL: ₹{t['netPnlInr']} | Reason: {t['exitReason']}")
