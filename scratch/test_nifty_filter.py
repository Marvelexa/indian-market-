import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.replay_engine import IndianPastDateReplayEngine

engine = IndianPastDateReplayEngine()
engine.set_date("2026-11-13", auto_play=False)

# Let's see Nifty's session bias:
day_bars = engine.by_date_5m.get("2026-11-13", {})
nifty_bars = day_bars.get("NIFTY", [])

print(f"Loaded {len(nifty_bars)} bars for NIFTY.")
