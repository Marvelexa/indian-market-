import json
import re

with open("scratch/all_day_broker_orders.json") as f:
    orders = json.load(f)

# Filter for orders between 09:15:00 and 15:15:00
# Also eliminate after-hours and pre-market (before 09:15)
trading_orders = []
for o in orders:
    ts = o["timestamp"]
    if ts == "UNKNOWN":
        continue
    # Only keep 09:15:00 to 15:15:00
    if "09:15:00" <= ts <= "15:15:00":
        trading_orders.append(o)

print(f"Total orders between 09:15 and 15:15: {len(trading_orders)}")
buys = [o for o in trading_orders if o["side"] == "BUY"]
sells = [o for o in trading_orders if o["side"] == "SELL"]
print(f"BUYs: {len(buys)}, SELLs: {len(sells)}")

# Look at all BUYs
print("\nChronological list of all BUY orders between 09:15 and 15:15:")
seen = set()
unique_trades = []
for i, b in enumerate(buys):
    key = (b["timestamp"][:5], b["symbol"], b["qty"], b["price"])
    # Check if duplicate order in quick succession
    is_dup = key in seen
    seen.add(key)
    unique_trades.append({
        "index": i + 1,
        "time": b["timestamp"],
        "symbol": b["symbol"],
        "qty": b["qty"],
        "price": b["price"],
        "seat": b["seat"],
        "tag": b["tag"],
        "is_dup": is_dup,
        "log_file": b["log_file"]
    })
    print(f"#{i+1:02d} | [{b['timestamp']}] BUY {b['qty']:>5}x {b['symbol']:<25} @ ₹{b['price']:>7.2f} | Seat: {b['seat']:<8} | Tag: {b['tag'][:35]} | Log: {b['log_file']}")

with open("scratch/legitimate_buys_0915_1515.json", "w") as f:
    json.dump(unique_trades, f, indent=2)
