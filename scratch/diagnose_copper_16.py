import pandas as pd
import numpy as np
import json

d = json.load(open('scratch/mcx_real_data/COPPER.json'))
df = pd.DataFrame(d)
df['dt'] = pd.to_datetime(df['timestamp'], unit='ms') + pd.Timedelta(hours=5, minutes=30)
df['date'] = df['dt'].dt.strftime('%Y-%m-%d')
df['time'] = df['dt'].dt.strftime('%H:%M')

d16 = df[df['date'] == '2026-11-16'].copy()
print("COPPER 2026-11-16 Summary:")
print(f"Candles count: {len(d16)}")
print(f"Open: {d16.iloc[0]['open']} at {d16.iloc[0]['time']}")
print(f"High: {d16['high'].max()}")
print(f"Low: {d16['low'].min()}")
print(f"Close: {d16.iloc[-1]['close']} at {d16.iloc[-1]['time']}")

# Check EMA50 and EMA200 on 5m across the whole dataset
closes = df['close'].values
ema50 = pd.Series(closes).ewm(span=50, adjust=False).mean().values
ema200 = pd.Series(closes).ewm(span=200, adjust=False).mean().values

d16['ema50'] = ema50[d16.index]
d16['ema200'] = ema200[d16.index]

print("\nKey timestamps on Nov 16:")
for t in ['10:20', '16:10', '20:45', '22:45']:
    row = d16[d16['time'] == t]
    if len(row) > 0:
        r = row.iloc[0]
        print(f"Time: {t} | Close: {r['close']} | EMA50: {r['ema50']:.2f} | EMA200: {r['ema200']:.2f} | Above EMA50? {r['close'] > r['ema50']} | Above EMA200? {r['close'] > r['ema200']}")
