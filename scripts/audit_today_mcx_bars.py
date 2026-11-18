import urllib.request
import json
import datetime

mcx_data = json.loads(urllib.request.urlopen('http://127.0.0.1:8000/api/mcx/candles-batch').read())

for sym in ['CRUDEOIL', 'SILVER', 'NATURALGAS', 'GOLD', 'COPPER']:
    bars = mcx_data[sym]
    today_bars = [c for c in bars if datetime.datetime.fromtimestamp(c['timestamp']/1000).date() == datetime.date(2026, 11, 16)]
    # filter market hours 09:00 to 23:20
    mkt_bars = [c for c in today_bars if 9 <= datetime.datetime.fromtimestamp(c['timestamp']/1000).hour < 23 or (datetime.datetime.fromtimestamp(c['timestamp']/1000).hour == 23 and datetime.datetime.fromtimestamp(c['timestamp']/1000).minute <= 20)]
    if mkt_bars:
        o = mkt_bars[0]['open']
        h = max(c['high'] for c in mkt_bars)
        l = min(c['low'] for c in mkt_bars)
        cl = mkt_bars[-1]['close']
        t0 = datetime.datetime.fromtimestamp(mkt_bars[0]['timestamp']/1000).strftime('%H:%M')
        t1 = datetime.datetime.fromtimestamp(mkt_bars[-1]['timestamp']/1000).strftime('%H:%M')
        print(f"{sym:12s} ({t0} to {t1}) Open: {o:9.2f} | High: {h:9.2f} | Low: {l:9.2f} | Close: {cl:9.2f} | Diff: {cl - o:+.2f}")
