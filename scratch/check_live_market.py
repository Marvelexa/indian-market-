import requests
import json

res = requests.get('http://127.0.0.1:8000/api/overview').json()

print("=== MARKET STATUS ===")
print(res.get('status'))

print("\n=== INDICES ===")
for idx in res.get('indices', []):
    print(f"{idx['clean_symbol']:<12}: LTP {idx['ltp']:>9.2f} | Chg {idx['change_pct']:>+6.2f}% | High {idx['high']:>9.2f} | Low {idx['low']:>9.2f}")

print("\n=== EQUITIES (14 Whitelist) ===")
green_count = 0
red_count = 0
for eq in res.get('equities', []):
    chg = eq['change_pct']
    if chg > 0:
        green_count += 1
    else:
        red_count += 1
    direction = "🟢" if chg >= 0 else "🔴"
    print(f"{direction} {eq['clean_symbol']:<14}: LTP {eq['ltp']:>9.2f} | Chg {chg:>+6.2f}% | High {eq['high']:>9.2f} | Low {eq['low']:>9.2f} | Vol {eq['volume']}")

total = green_count + red_count
breadth_bullish = (green_count / total * 100) if total > 0 else 0
print(f"\nMARKET BREADTH: {breadth_bullish:.1f}% Bullish ({green_count} Green / {red_count} Red)")

# Check sniper scan
scan_res = requests.get('http://127.0.0.1:8000/api/sniper/scan').json()
print("\n=== SNIPER SIGNALS ===")
print(f"Total signals: {scan_res.get('count', 0)}")
for sig in scan_res.get('signals', []):
    print(json.dumps(sig, indent=2))
