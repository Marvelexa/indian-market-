import sys
sys.path.insert(0, '.')
from backend.replay_engine import IndianPastDateReplayEngine

engine = IndianPastDateReplayEngine.get_instance()
days = [d['date'] if isinstance(d, dict) else d for d in engine.available_days]

total_pnl = 0.0
total_trades = 0
total_wins = 0

for d in days:
    engine.set_date(d, auto_play=False, speed=1)
    for sec in range(0, 22500, 30):
        engine.advance_seconds(30)
    w = engine.get_state()['wallet']
    day_pnl = w['realizedPnlInr']
    total_pnl += day_pnl
    total_trades += w['totalTrades']
    total_wins += w['wins']

print("==================================================")
print("60-DAY MULTI-ASSET INSTITUTIONAL 20K TARGET BACKTEST")
print(f"Total Days: {len(days)}")
print(f"Total Trades: {total_trades}")
print(f"Wins: {total_wins}, Losses: {total_trades - total_wins}")
win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
print(f"Win Rate: {win_rate:.1f}%")
print(f"Total Realized PnL: +₹{total_pnl:,.2f}")
print("==================================================")
