import re
import json

log_path = r"C:\Users\Rajesh\.gemini\antigravity\brain\ad428b8d-94bd-4900-ba0c-e90e8694fd02\.system_generated\tasks\task-643.log"
content = open(log_path, encoding='utf-8', errors='ignore').read()

# Let's split by [BROKER ORDER]
chunks = content.split("⚡ [BROKER ORDER] ")
print(f"Total chunks found: {len(chunks)}")

orders = []
for chunk in chunks[1:]:
    # First line is order info
    lines = chunk.splitlines()
    first_line = lines[0].strip()
    
    # Example: BUY 475x BHARTIARTL 2160 CE @ ₹47.5 | Seat: TREND_1 | Tag: PA_STRUCTURE_BREAKOUT_BUY...
    m = re.match(r"(BUY|SELL)\s+(\d+)x\s+([^@|]+?)\s+@\s+₹([\d.]+)\s+\|\s+Seat:\s+(\S+)\s+\|\s+Tag:\s+(.*)", first_line)
    if not m:
        continue
    
    side = m.group(1)
    qty = int(m.group(2))
    symbol = m.group(3).strip()
    price = float(m.group(4))
    seat = m.group(5)
    tag = m.group(6).strip()
    
    # Now find timestamp from response in the chunk
    ts = None
    m_ts = re.search(r"timestamp:\s*'([^']+)'", chunk)
    if m_ts:
        ts = m_ts.group(1)
    else:
        # Check if there is an ISO timestamp or HH:MM:SS in the text
        m_time = re.search(r"(\d{2}:\d{2}:\d{2})", chunk[:500])
        if m_time:
            ts = m_time.group(1)
            
    orders.append({
        "side": side,
        "qty": qty,
        "symbol": symbol,
        "price": price,
        "seat": seat,
        "tag": tag,
        "timestamp": ts or "UNKNOWN"
    })

print(f"Parsed {len(orders)} total orders.")

buys = [o for o in orders if o["side"] == "BUY"]
sells = [o for o in orders if o["side"] == "SELL"]
print(f"Total BUYs: {len(buys)}, Total SELLs: {len(sells)}")

# Save to json for further analysis
with open("scratch/all_parsed_orders.json", "w") as f:
    json.dump(orders, f, indent=2)

print("\nFirst 15 BUY orders:")
for b in buys[:15]:
    print(f"[{b['timestamp']}] BUY {b['qty']}x {b['symbol']} @ ₹{b['price']} (Seat: {b['seat']}) Tag: {b['tag']}")
