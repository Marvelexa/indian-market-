import pandas as pd
import json

d = json.load(open('scratch/mcx_real_data/COPPER.json'))
df = pd.DataFrame(d)
df['dt'] = pd.to_datetime(df['timestamp'], unit='ms') + pd.Timedelta(hours=5, minutes=30)
df['date'] = df['dt'].dt.strftime('%Y-%m-%d')
df['time'] = df['dt'].dt.strftime('%H:%M')

c16 = df[df['date'] == '2026-11-16']
idx_1020 = c16[c16['time'] == '10:20'].index[0]
print("COPPER CANDLES AROUND 10:20 on Nov 16:")
for i in range(idx_1020 - 5, idx_1020 + 6):
    r = df.iloc[i]
    print(f"Time: {r['time']} | Open: {r['open']} | High: {r['high']} | Low: {r['low']} | Close: {r['close']} | Vol: {r['volume']}")
