import requests
import json

r = requests.get('http://127.0.0.1:8000/api/candles-batch?timeframe=5D').json()

print("CURRENT STATUS OF 14 STOCKS (10:54 AM IST):")
print("-" * 65)

bulls = []
bears = []
neutrals = []

for sym, candles in r.items():
    if not sym.endswith('.NS') and sym not in ['NIFTY', 'BANKNIFTY']:
        continue
    if len(candles) < 25:
        continue
        
    c0 = candles[-1]
    closes = [c['close'] for c in candles]
    last_close = closes[-1]
    
    # Calculate VWAP
    recent75 = candles[-75:]
    pv = sum(((c['high'] + c['low'] + c['close'])/3.0) * max(c.get('volume', 1), 1) for c in recent75)
    vsum = sum(max(c.get('volume', 1), 1) for c in recent75)
    vwap = pv / vsum if vsum > 0 else last_close
    
    # EMA9 and EMA21
    k9 = 2.0 / 10
    k21 = 2.0 / 22
    e9 = closes[0]
    e21 = closes[0]
    for cl in closes:
        e9 = cl * k9 + e9 * (1 - k9)
        e21 = cl * k21 + e21 * (1 - k21)
        
    clean = sym.replace('.NS', '').replace('^', '')
    if last_close > vwap and e9 >= e21:
        bulls.append((clean, last_close, vwap, e9, e21))
    elif last_close < vwap and e9 <= e21:
        bears.append((clean, last_close, vwap, e9, e21))
    else:
        neutrals.append((clean, last_close, vwap, e9, e21))

print(f"🟢 BULLISH ({len(bulls)}): {[b[0] for b in bulls]}")
print(f"🔴 BEARISH ({len(bears)}): {[b[0] for b in bears]}")
print(f"🟡 NEUTRAL/CHOP ({len(neutrals)}): {[b[0] for b in neutrals]}")
print("-" * 65)
