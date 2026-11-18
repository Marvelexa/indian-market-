import json, datetime

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
bars = json.load(open("d:/new start/.cache_indian_market_60d/BANKNIFTY_5m.json"))
today_bars = [b for b in bars if datetime.datetime.fromtimestamp(b["timestamp"]/1000, IST).strftime("%Y-%m-%d") == "2026-11-16"]

print(f"Total BankNifty bars today: {len(today_bars)}")
for i, b in enumerate(today_bars):
    t = datetime.datetime.fromtimestamp(b["timestamp"]/1000, IST).strftime("%H:%M")
    print(f"Bar {i:2d} ({t}): O={b['open']:.1f} H={b['high']:.1f} L={b['low']:.1f} C={b['close']:.1f}")
