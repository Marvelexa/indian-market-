import sys
sys.path.insert(0, r"d:\new start")
import json, datetime

# Test what happens when options SL is evaluated cleanly without synthetic wick kill
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS

# Let's inspect
print("Testing clean replay...")
