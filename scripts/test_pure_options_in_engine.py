import sys
sys.path.insert(0, r"d:\new start")
import json, datetime

from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS

engine = IndianPastDateReplayEngine.get_instance()
print("Engine instance retrieved.")
