import glob
import re
import json
import os

today_logs = [
    r"C:\Users\Rajesh\.gemini\antigravity\brain\ad428b8d-94bd-4900-ba0c-e90e8694fd02\.system_generated\tasks\task-1422.log",
    r"C:\Users\Rajesh\.gemini\antigravity\brain\ad428b8d-94bd-4900-ba0c-e90e8694fd02\.system_generated\tasks\task-1614.log",
    r"C:\Users\Rajesh\.gemini\antigravity\brain\ad428b8d-94bd-4900-ba0c-e90e8694fd02\.system_generated\tasks\task-1750.log",
    r"C:\Users\Rajesh\.gemini\antigravity\brain\ad428b8d-94bd-4900-ba0c-e90e8694fd02\.system_generated\tasks\task-1769.log",
    r"C:\Users\Rajesh\.gemini\antigravity\brain\ad428b8d-94bd-4900-ba0c-e90e8694fd02\.system_generated\tasks\task-2077.log",
    r"C:\Users\Rajesh\.gemini\antigravity\brain\ad428b8d-94bd-4900-ba0c-e90e8694fd02\.system_generated\tasks\task-2296.log",
    r"C:\Users\Rajesh\.gemini\antigravity\brain\ad428b8d-94bd-4900-ba0c-e90e8694fd02\.system_generated\tasks\task-3486.log"
]

all_buys = []
for log in today_logs:
    if not os.path.exists(log):
        continue
    content = open(log, encoding='utf-8', errors='ignore').read()
    chunks = content.split("[BROKER ORDER] ")
    for chunk in chunks[1:]:
        first_line = chunk.splitlines()[0].strip()
        m = re.match(r"(BUY)\s+(\d+)x\s+([^@|]+?)\s+@\s+₹([\d.]+)\s+\|\s+Seat:\s+(\S+)\s+\|\s+Tag:\s+(.*)", first_line)
        if not m:
            continue
        qty = int(m.group(2))
        sym = m.group(3).strip()
        price = float(m.group(4))
        seat = m.group(5)
        tag = m.group(6).strip()
        
        # Extract timestamp
        m_time = re.search(r"\[(\d{2}:\d{2}:\d{2})\s+IST\]", chunk[:500])
        ts = m_time.group(1) if m_time else None
        if not ts:
            m_time2 = re.search(r"(\d{2}:\d{2}:\d{2})", chunk[:500])
            ts = m_time2.group(1) if m_time2 else "UNKNOWN"
            
        all_buys.append({
            "log": os.path.basename(log),
            "time": ts,
            "symbol": sym,
            "qty": qty,
            "price": price,
            "seat": seat,
            "tag": tag
        })

print(f"Total BUY orders collected from today logs: {len(all_buys)}")
with open("scratch/today_buys_all.json", "w") as f:
    json.dump(all_buys, f, indent=2)

for b in all_buys[:25]:
    print(f"{b['time']} | BUY {b['qty']}x {b['symbol']} @ ₹{b['price']} | Seat: {b['seat']}")
