import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scratch.test_super_accuracy_strategy import SuperStrategyReplayEngine, TOTAL_DAY_SECONDS

eng = SuperStrategyReplayEngine(min_start_sec=2700, min_breadth_pct=70.0, index_lots=1)
oct_dates = [d for d in eng.sorted_dates if "-10-" in d]

print(f"{'Date':<12} | {'Weekday':<9} | {'Net PnL':<12} | {'Trades':<8} | {'WR':<7} | {'Category'}")
print("-" * 75)

for d in oct_dates:
    eng.set_date(d, auto_play=True)
    eng.is_running = True
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    st = eng.get_state()
    w = st['wallet']
    pnl = w['realizedPnlInr']
    trades = w['totalTrades']
    wins = w['wins']
    wr = (wins / max(1, trades)) * 100.0
    day_meta = next((m for m in eng.available_days if m['date'] == d), {})
    cat = day_meta.get('category', '')
    weekday = day_meta.get('weekday', '')
    pnl_str = f"+INR {pnl:,.2f}" if pnl >= 0 else f"-INR {abs(pnl):,.2f}"
    print(f"{d:<12} | {weekday:<9} | {pnl_str:<12} | {trades:>2} (W:{wins:>2}) | {wr:>5.1f}% | {cat}")
