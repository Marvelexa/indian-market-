import urllib.request
import json
import datetime
from zoneinfo import ZoneInfo
import pandas as pd

ist = ZoneInfo('Asia/Kolkata')
url = 'https://query1.finance.yahoo.com/v8/finance/chart/CL=F?interval=1h&range=3mo'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req)
data = json.loads(resp.read().decode())['chart']['result'][0]

ts = data['timestamp']
quote = data['indicators']['quote'][0]

bars = []
for i in range(len(ts)):
    t = ts[i]
    o = quote['open'][i]
    h = quote['high'][i]
    l = quote['low'][i]
    c = quote['close'][i]
    v = quote['volume'][i]
    if o is None or c is None:
        continue
    dt = datetime.datetime.fromtimestamp(t, ist)
    bars.append({
        "timestamp": t,
        "datetime": dt,
        "date": dt.strftime("%Y-%m-%d"),
        "time": dt.strftime("%H:%M:%S"),
        "open": round(o, 2),
        "high": round(h, 2),
        "low": round(l, 2),
        "close": round(c, 2),
        "volume": v or 1
    })

df = pd.DataFrame(bars)
print(f"Total CL=F 1h bars fetched: {len(df)}")
print(f"Start: {df['date'].min()} {df['time'].min()} | End: {df['date'].max()} {df['time'].max()}")

# Filter to 2026-08-18 to 2026-11-13
df_audit = df[(df['date'] >= '2026-08-18') & (df['date'] <= '2026-11-13')].copy()
print(f"Audit period bars: {len(df_audit)}")
print(f"Unique dates: {df_audit['date'].nunique()}")
