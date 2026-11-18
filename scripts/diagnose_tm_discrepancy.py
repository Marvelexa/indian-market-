import sys
sys.path.insert(0, r"d:\new start")
from backend.replay_engine import IndianPastDateReplayEngine, WHITELIST_14_SYMBOLS

# Let's inspect what happens when:
# 1. NIFTY lot is 50, BANKNIFTY lot is 30 (2 Lots as in simulate_options_today.py)
# 2. Daily limit on NIFTY/BANKNIFTY is 4 (so 11:45 AM trade is taken)
# 3. Stock trades only taken if RVOL/trend is strong (skipping weak chop scalps)

# Let's run a test with replay engine logic
engine = IndianPastDateReplayEngine.get_instance()
print("Indexed days:", len(engine.sorted_dates))
