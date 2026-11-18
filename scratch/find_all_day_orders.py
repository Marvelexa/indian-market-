import glob
import os
import re
import json

tasks_dir = r"C:\Users\Rajesh\.gemini\antigravity\brain\ad428b8d-94bd-4900-ba0c-e90e8694fd02\.system_generated\tasks"
log_files = sorted(glob.glob(os.path.join(tasks_dir, "task-*.log")), key=os.path.getmtime)

print(f"Found {len(log_files)} task logs.")

all_orders = []

for log_file in log_files:
    fname = os.path.basename(log_file)
    try:
        content = open(log_file, encoding='utf-8', errors='ignore').read()
    except Exception as e:
        continue
    
    if "[BROKER ORDER]" not in content:
        continue
        
    chunks = content.split("⚡ [BROKER ORDER] ")
    print(f"{fname}: {len(chunks)-1} broker order chunks")
    
    for chunk in chunks[1:]:
        lines = chunk.splitlines()
        first_line = lines[0].strip()
        
        m = re.match(r"(BUY|SELL)\s+(\d+)x\s+([^@|]+?)\s+@\s+₹([\d.]+)\s+\|\s+Seat:\s+(\S+)\s+\|\s+Tag:\s+(.*)", first_line)
        if not m:
            continue
        
        side = m.group(1)
        qty = int(m.group(2))
        symbol = m.group(3).strip()
        price = float(m.group(4))
        seat = m.group(5)
        tag = m.group(6).strip()
        
        ts = None
        m_ts = re.search(r"timestamp:\s*'([^']+)'", chunk)
        if m_ts:
            ts = m_ts.group(1)
        else:
            m_time = re.search(r"(\d{2}:\d{2}:\d{2})", chunk[:500])
            if m_time:
                ts = m_time.group(1)
                
        all_orders.append({
            "log_file": fname,
            "side": side,
            "qty": qty,
            "symbol": symbol,
            "price": price,
            "seat": seat,
            "tag": tag,
            "timestamp": ts or "UNKNOWN"
        })

print(f"\nTotal collected orders across ALL logs: {len(all_orders)}")

# Check timestamps distribution
buys = [o for o in all_orders if o["side"] == "BUY"]
sells = [o for o in all_orders if o["side"] == "SELL"]
print(f"Total BUYs: {len(buys)}, Total SELLs: {len(sells)}")

with open("scratch/all_day_broker_orders.json", "w") as f:
    json.dump(all_orders, f, indent=2)

# Print timestamp range
valid_ts = [o["timestamp"] for o in all_orders if o["timestamp"] != "UNKNOWN"]
if valid_ts:
    print(f"Timestamp range: min {min(valid_ts)} to max {max(valid_ts)}")
