import json
import re

with open("scratch/all_day_broker_orders.json") as f:
    orders = json.load(f)

print(f"Total raw orders: {len(orders)}")

# Let's inspect the BUY orders across the day
# We want to identify every unique position / trade opened between 09:15 and 15:15
# Grouping by log_file or sorting chronologically
for log_file in ["task-194.log", "task-332.log", "task-503.log", "task-569.log", "task-643.log"]:
    log_orders = [o for o in orders if o["log_file"] == log_file]
    buys = [o for o in log_orders if o["side"] == "BUY"]
    sells = [o for o in log_orders if o["side"] == "SELL"]
    print(f"\n--- {log_file} --- Total: {len(log_orders)} (BUYs: {len(buys)}, SELLs: {len(sells)})")
    if buys:
        print(f"  First BUY: [{buys[0]['timestamp']}] {buys[0]['symbol']} @ ₹{buys[0]['price']}")
        print(f"  Last BUY:  [{buys[-1]['timestamp']}] {buys[-1]['symbol']} @ ₹{buys[-1]['price']}")
    for b in buys:
        print(f"    [{b['timestamp']}] BUY {b['qty']}x {b['symbol']} @ ₹{b['price']} | {b['seat']} | {b['tag'][:40]}")
