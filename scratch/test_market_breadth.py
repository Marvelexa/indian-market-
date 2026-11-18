import os
import sys
import json
import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.replay_engine import WHITELIST_14_SYMBOLS, IndianPastDateReplayEngine

eng = IndianPastDateReplayEngine()
oct_dates = [d for d in eng.sorted_dates if "-10-" in d]

print(f"Testing Market Breadth across all {len(oct_dates)} days of October 2026:")
print("-" * 85)

for d in oct_dates:
    day_bars_5m = eng.by_date_5m.get(d, {})
    # Check breadth at 09:45 AM (bar index 6) and 10:15 AM (bar index 12)
    line = f"{d} | "
    for check_bar in [6, 12]:
        time_str = "09:45 AM" if check_bar == 6 else "10:15 AM"
        bull_count = 0
        bear_count = 0
        total_syms = 0
        
        for sym in WHITELIST_14_SYMBOLS:
            bars = day_bars_5m.get(sym, [])
            if len(bars) > check_bar:
                sess = bars[:check_bar + 1]
                c = float(bars[check_bar]["close"])
                pv = sum(((float(b["high"]) + float(b["low"]) + float(b["close"])) / 3.0) * max(float(b.get("volume", 1)), 1.0) for b in sess)
                v = sum(max(float(b.get("volume", 1)), 1.0) for b in sess)
                vwap = (pv / v) if v > 0 else c
                if c > vwap:
                    bull_count += 1
                else:
                    bear_count += 1
                total_syms += 1
        
        ratio = max(bull_count, bear_count) / max(1, total_syms) * 100.0
        dominant = "BULL" if bull_count > bear_count else ("BEAR" if bear_count > bull_count else "SPLIT")
        line += f"[{time_str}: {dominant:<5} {bull_count:>2}U/{bear_count:>2}D ({ratio:>4.0f}%)]  "
    print(line)
