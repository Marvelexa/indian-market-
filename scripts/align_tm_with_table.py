import sys
sys.path.insert(0, r"d:\new start")
import json, datetime

# Let's inspect the exact trade execution difference
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS

engine = IndianPastDateReplayEngine.get_instance()
engine.set_date("2026-11-16", auto_play=True, speed=300)

# Let's run a test where:
# 1. Option seats are pure index options (Nifty 50, BankNifty 30)
# 2. Stock trades follow strict AGENTS.md rules (No weak chop scalps)
# 3. Check what trades fire and what PnL is achieved
print(f"Current Date: {engine.current_date}")
