import os
import sys
import numpy as np
sys.path.insert(0, os.path.abspath('.'))
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS, WHITELIST_14_SYMBOLS, INDEX_SET, DISPLAY_NAMES

# Standard NSE F&O Lot Sizes for Whitelist Stocks
STOCK_FO_LOT_SIZES = {
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "FINNIFTY": 25,
    "SENSEX": 10,
    "RELIANCE": 250,
    "HDFCBANK": 550,
    "ICICIBANK": 700,
    "SBIN": 750,
    "INFY": 400,
    "TCS": 175,
    "TATAMOTORS": 500,
    "AXISBANK": 625,
    "LT": 150,
    "BAJFINANCE": 125
}

# ATM Strike step sizes
STRIKE_STEPS = {
    "NIFTY": 50,
    "BANKNIFTY": 100,
    "FINNIFTY": 50,
    "SENSEX": 100,
    "RELIANCE": 20,
    "HDFCBANK": 10,
    "ICICIBANK": 10,
    "SBIN": 5,
    "INFY": 10,
    "TCS": 50,
    "TATAMOTORS": 5,
    "AXISBANK": 10,
    "LT": 50,
    "BAJFINANCE": 50
}

print("Script template ready")
