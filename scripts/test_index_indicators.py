import urllib.request
import json
import datetime
from typing import List, Dict

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
TODAY = "2026-11-16"

req = urllib.request.urlopen("http://127.0.0.1:8000/api/candles-batch?timeframe=5D")
data = json.loads(req.read().decode("utf-8"))

def compute_ema(series: List[float], period: int) -> float:
    if len(series) < period:
        return series[-1] if series else 0.0
    k = 2.0 / (period + 1.0)
    ema = sum(series[:period]) / period
    for val in series[period:]:
        ema = val * k + ema * (1.0 - k)
    return ema

def compute_vwap(candles: List[Dict]) -> float:
    pv = sum(c["close"] * c.get("volume", 1) for c in candles)
    v = sum(c.get("volume", 1) for c in candles)
    return pv / v if v > 0 else (candles[-1]["close"] if candles else 0.0)

for sym in ["NIFTY", "BANKNIFTY"]:
    all_candles = data.get(sym, [])
    # Find start index of today
    today_candles = [c for c in all_candles if datetime.datetime.fromtimestamp(c["timestamp"]/1000, IST).strftime("%Y-%m-%d") == TODAY]
    print(f"\n=== {sym} Today ({len(today_candles)} bars) ===")
    for i in range(len(today_candles)):
        # all history up to this candle
        cur_c = today_candles[i]
        hist = [c for c in all_candles if c["timestamp"] <= cur_c["timestamp"]]
        closes = [c["close"] for c in hist]
        e9 = compute_ema(closes, 9)
        e21 = compute_ema(closes, 21)
        # intraday vwap only from today's candles
        vw = compute_vwap(today_candles[:i+1])
        t_str = datetime.datetime.fromtimestamp(cur_c["timestamp"]/1000, IST).strftime("%H:%M")
        c = cur_c["close"]
        bias = "BULL" if c > vw and e9 >= e21 else ("BEAR" if c < vw and e9 <= e21 else "CHOP")
        print(f"{t_str} | Close={c:.1f} VWAP={vw:.1f} EMA9={e9:.1f} EMA21={e21:.1f} | Bias={bias}")
