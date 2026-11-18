import sys
sys.path.insert(0, r"d:\new start")
import json, datetime

# Exact Option Replay Engine with 15m intervals (matching simulate_options_today.py)
from backend.replay_engine import IndianPastDateReplayEngine

engine = IndianPastDateReplayEngine.get_instance()
day_data_15m = engine.by_date_15m.get("2026-11-16", {})
nifty_15m = day_data_15m.get("NIFTY", [])
bn_15m = day_data_15m.get("BANKNIFTY", [])
print(f"15m candles: NIFTY={len(nifty_15m)}, BANKNIFTY={len(bn_15m)}")
