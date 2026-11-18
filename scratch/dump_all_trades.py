import urllib.request
import json

try:
    data = json.loads(urllib.request.urlopen('http://localhost:8000/api/portfolio').read())
    orders = data.get('orders', [])
    positions = data.get('positions', [])
    print(f"=== BACKEND ORDERS ({len(orders)}) ===")
    for o in orders:
        print(f"ID: {o.get('order_id')} | Time: {o.get('time')} | Sym: {o.get('symbol')} | Side: {o.get('side')} | Qty: {o.get('quantity')} | Price: {o.get('price')} | Exit: {o.get('exit_price')} | PnL: {o.get('realized_pnl')} | Status: {o.get('status')}")
    
    print(f"\n=== BACKEND OPEN POSITIONS ({len(positions)}) ===")
    for p in positions:
        print(f"Sym: {p.get('clean_symbol')} | Side: {p.get('side')} | Qty: {p.get('quantity')} | Entry: {p.get('avg_price')} | LTP: {p.get('current_ltp')} | PnL: {p.get('pnl')} ({p.get('pnl_pct')}%) | SL: {p.get('sl_price')} | TP: {p.get('tp_price')}")
except Exception as e:
    print("Error:", e)
