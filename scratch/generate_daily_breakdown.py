import urllib.request
import json
import datetime
from zoneinfo import ZoneInfo

url = 'https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=1d&range=1y'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req)
data = json.loads(resp.read().decode())['chart']['result'][0]

ts = data['timestamp']
q = data['indicators']['quote'][0]
ist = ZoneInfo('Asia/Kolkata')

days_2026 = []
for i in range(len(ts)):
    dt = datetime.datetime.fromtimestamp(ts[i], ist)
    d = dt.strftime('%Y-%m-%d')
    if d.startswith('2026-') and q['open'][i] is not None and q['close'][i] is not None:
        o = round(float(q['open'][i]), 2)
        h = round(float(q['high'][i]), 2)
        l = round(float(q['low'][i]), 2)
        c = round(float(q['close'][i]), 2)
        v = q['volume'][i] or 0
        chg = round(((c - o) / o) * 100.0, 2)
        rng = round(h - l, 1)
        days_2026.append({
            'date': d,
            'weekday': dt.strftime('%a'),
            'open': o,
            'high': h,
            'low': l,
            'close': c,
            'volume': v,
            'chgPct': chg,
            'rangePts': rng
        })

print(f"Total valid trading days fetched: {len(days_2026)}")
months = {}
for d in days_2026:
    m = d['date'][:7]
    if m not in months:
        months[m] = []
    months[m].append(d)

for m, mdays in sorted(months.items()):
    print(f"{m}: {len(mdays)} days | {mdays[0]['date']} to {mdays[-1]['date']}")
