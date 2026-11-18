import urllib.request
import json
import datetime

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
TODAY = "2026-11-16"

req = urllib.request.urlopen("http://127.0.0.1:8000/api/candles-batch?timeframe=5D")
data = json.loads(req.read().decode("utf-8"))

for s in ["NIFTY", "BANKNIFTY"]:
    candles = [c for c in data.get(s, []) if datetime.datetime.fromtimestamp(c["timestamp"] / 1000, IST).strftime("%Y-%m-%d") == TODAY]
    print(f"\n{s} ({len(candles)} candles):")
    for i, c in enumerate(candles):
        t = datetime.datetime.fromtimestamp(c["timestamp"] / 1000, IST).strftime("%H:%M")
        print(f"  {t} | O={c['open']:.1f} H={c['high']:.1f} L={c['low']:.1f} C={c['close']:.1f}")
