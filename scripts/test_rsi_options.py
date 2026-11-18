import sys
sys.path.insert(0, r"d:\new start")

from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS

engine = IndianPastDateReplayEngine.get_instance()
print("Engine ready for RSI test.")
