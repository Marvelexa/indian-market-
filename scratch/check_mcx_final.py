import urllib.request
import json

try:
    res = urllib.request.urlopen("http://127.0.0.1:3006/api/mcx/status", timeout=3)
    data = json.loads(res.read().decode())
    print("Market Open:", data.get("isMarketOpen"))
    print("Clock:", data.get("istTimeStr"))
    print("Active positions count:", len(data.get("activePositions", [])))
    print("Closed trades count:", len(data.get("closedTrades", [])))
    
    closed = data.get("closedTrades", [])
    total_net = sum(t.get("netPnlInr", 0) for t in closed)
    print(f"Total Realized Net PnL: ₹{total_net:,.2f}")
    
    print("\n--- ALL CLOSED TRADES ---")
    for idx, t in enumerate(closed):
        sym = t.get("commoditySymbol")
        opt = t.get("optionSymbol")
        entry = t.get("entryPremium")
        exit_p = t.get("exitPremium")
        pnl = t.get("netPnlInr")
        reason = t.get("exitReason")
        closed_at = t.get("closedAtIst")
        print(f"#{idx+1:02d} | {sym:<10} | {opt:<24} | Entry ₹{entry:>7.2f} -> Exit ₹{exit_p:>7.2f} | PnL: ₹{pnl:>+9.2f} | {reason} | Closed: {closed_at}")
        
    active = data.get("activePositions", [])
    if active:
        print("\n--- ACTIVE POSITIONS ---")
        for a in active:
            print(a)
            
except Exception as e:
    print("Error querying MCX:", e)
