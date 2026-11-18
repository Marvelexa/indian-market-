import urllib.request
import json
import datetime

mcx_data = json.loads(urllib.request.urlopen('http://127.0.0.1:8000/api/mcx/candles-batch').read())

print("=" * 80)
print("DEEP DIVE: CRUDEOIL PEAK REVERSAL ON 16-NOV-2026")
print("=" * 80)

crude = mcx_data['CRUDEOIL']
# Look at bars between 11:30 and 13:00 where Crude Oil topped out at 7875
for c in crude:
    dt = datetime.datetime.fromtimestamp(c['timestamp']/1000)
    if dt.date() == datetime.date(2026, 11, 16) and 11 <= dt.hour <= 14:
        t_str = dt.strftime('%H:%M')
        o, h, l, cl = c['open'], c['high'], c['low'], c['close']
        rng = h - l
        body = abs(cl - o)
        uw = (h - max(o, cl)) / max(rng, 0.01)
        lw = (min(o, cl) - l) / max(rng, 0.01)
        print(f"Time: {t_str} | O: {o:7.2f} | H: {h:7.2f} | L: {l:7.2f} | C: {cl:7.2f} | UpperWick: {uw:4.2f} | LowerWick: {lw:4.2f} | Dir: {'GREEN' if cl > o else 'RED'}")

print("\n" + "=" * 80)
print("DEEP DIVE: SILVER PEAK REVERSAL ON 16-NOV-2026")
print("=" * 80)

silver = mcx_data['SILVER']
# Look at bars between 09:00 and 12:00 where Silver topped out at 135196
for c in silver:
    dt = datetime.datetime.fromtimestamp(c['timestamp']/1000)
    if dt.date() == datetime.date(2026, 11, 16) and 9 <= dt.hour <= 12 and c['high'] > 134800:
        t_str = dt.strftime('%H:%M')
        o, h, l, cl = c['open'], c['high'], c['low'], c['close']
        print(f"Time: {t_str} | O: {o:9.2f} | H: {h:9.2f} | L: {l:9.2f} | C: {cl:9.2f}")
