import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS

def simulate_speed(speed, date="2026-11-02"):
    eng = IndianPastDateReplayEngine()
    eng.set_date(date, auto_play=True, speed=speed)
    
    # Simulate simulation loop steps
    # In _simulation_loop, nominal_step = speed * dt (dt is ~0.1s)
    # advance_step = max(5, ((nominal_step + 2) // 5) * 5)
    nominal_step = int(round(speed * 0.1))
    advance_step = max(5, ((nominal_step + 2) // 5) * 5)
    
    while eng.second_of_day < TOTAL_DAY_SECONDS and eng.is_running:
        eng.advance_seconds(advance_step)
        
    st = eng.get_state()
    w = st['wallet']
    return w['realizedPnlInr'], w['totalTrades'], w['wins'], len(eng.closed_ledger)

print(f"Testing Reproducibility on 2026-11-02 across 8 different speeds:")
results = []
for spd in [1, 5, 10, 30, 60, 150, 300, 600]:
    pnl, trades, wins, closed_cnt = simulate_speed(spd)
    print(f"  Speed {spd:>3}x -> Net PnL: ₹{pnl:>9,.2f} | Trades: {trades} | Wins: {wins}")
    results.append(pnl)

all_same = len(set(results)) == 1
print(f"\nAre all 8 speeds 100% mathematically identical? {all_same}")
