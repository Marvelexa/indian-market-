import sys
sys.path.insert(0, r"d:\new start")
from backend.replay_engine import IndianPastDateReplayEngine, WHITELIST_14_SYMBOLS

engine = IndianPastDateReplayEngine.get_instance()
target_date = "2026-11-16"
engine.set_date(target_date, auto_play=True, speed=300)

# Pre-populate warm history
target_idx = engine.sorted_dates.index(target_date)
prev_dates = engine.sorted_dates[max(0, target_idx - 2):target_idx]
engine.warm_history = {}
for s in WHITELIST_14_SYMBOLS:
    pb = []
    for pd in prev_dates:
        pb.extend(engine.by_date_5m.get(pd, {}).get(s, []))
    engine.warm_history[s] = pb[-40:]

print(f"Warm history loaded for {len(engine.warm_history)} symbols.")
