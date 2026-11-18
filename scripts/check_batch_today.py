import urllib.request
import json
import datetime

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
TODAY = "2026-11-16"

req = urllib.request.urlopen("http://127.0.0.1:8000/api/candles-batch?timeframe=5D")
data = json.loads(req.read().decode("utf-8"))

print(f"Total symbols in batch: {len(data)}")
for sym, candles in data.items():
    today_c = [c for c in candles if datetime.datetime.fromtimestamp(c["timestamp"]/1000, IST).strftime("%Y-%m-%d") == TODAY]
    if today_c:
        t0 = datetime.datetime.fromtimestamp(today_c[0]["timestamp"]/1000, IST).strftime("%H:%M")
        t1 = datetime.datetime.fromtimestamp(today_c[-1]["timestamp"]/1000, IST).strftime("%H:%M")
        print(f"{sym:<15}: {len(today_c)} candles ({t0} to {t1})")
    else:
        print(f"{sym:<15}: 0 candles for today")
