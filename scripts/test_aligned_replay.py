import sys
sys.path.insert(0, r"d:\new start")
import datetime
from backend.replay_engine import IndianPastDateReplayEngine, WHITELIST_14_SYMBOLS, TOTAL_DAY_SECONDS

# Let's see: what if the Time Machine runs the exact Option trades from simulate_options_today.py?
# In simulate_options_today.py:
# BankNifty entry at 09:30 AM (O=61346.8 C=61392.3) -> Reached TP6 (+₹3,000) at 09:45 (High=61677.1)!
# Nifty entry at 09:30 AM (O=25232.5 C=25264.5) -> Reached TP2 (+₹700) at 10:00!
# At 11:45 AM: BankNifty entry (O=61389.9 C=61387.3) -> Reached TP6 (+₹3,000) at 12:00 (High=61659.0)!
# At 11:45 AM: Nifty entry -> Reached TP2 (+₹700) at 12:15!
# At 12:00 PM: BankNifty entry -> Reached TP1 (+₹300) at 12:30!
# At 12:45 PM: BankNifty entry -> Reached TP2 (+₹700) at 13:15!

# Total Option PnL was +₹4,877.69!

# And what about Stocks?
# In simulate_today.py:
# HDFCBANK: +₹615.91
# LT: +₹1,440.50
# RELIANCE: +₹138.59
# TCS: +₹147.64
# BAJFINANCE: +₹142.64
# ICICIBANK: -₹1,617.23
# LT: -₹1,694.91
print("Checking trade alignment...")
