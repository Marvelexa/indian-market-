import sys, os, random
sys.path.insert(0, os.path.abspath('.'))
from backend.replay_engine import IndianPastDateReplayEngine

def run_loop_sim(seed_val):
    random.seed(seed_val)
    engine = IndianPastDateReplayEngine()
    engine.set_date('2026-11-02', auto_play=True, speed=300)
    
    while engine.is_running and engine.second_of_day < 22500:
        dt = random.uniform(0.08, 0.12)
        advance_step = max(1, int(round(engine.speed * max(0.05, min(0.5, dt)))))
        engine.advance_seconds(advance_step)
        
    return engine

e1 = run_loop_sim(1)
e2 = run_loop_sim(3)

print(f"=== RUN 1 TRADES (PnL: {e1.realized_pnl_inr}) ===")
for t in e1.closed_ledger:
    print(f"  {t['symbol']:12} {t['side']} En:{t['entryPrice']} Ex:{t['exitPrice']} PnL:{t['netPnlInr']:+8.1f} | {t['exitReason']}")

print(f"\n=== RUN 2 TRADES (PnL: {e2.realized_pnl_inr}) ===")
for t in e2.closed_ledger:
    print(f"  {t['symbol']:12} {t['side']} En:{t['entryPrice']} Ex:{t['exitPrice']} PnL:{t['netPnlInr']:+8.1f} | {t['exitReason']}")
