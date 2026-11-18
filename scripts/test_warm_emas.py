import sys
sys.path.insert(0, r"d:\new start")
from backend.replay_engine import IndianPastDateReplayEngine

engine = IndianPastDateReplayEngine.get_instance()
target_date = "2026-11-16"
idx = engine.sorted_dates.index(target_date)
prev_dates = engine.sorted_dates[max(0, idx - 2):idx]

for sym in ["NIFTY", "BANKNIFTY"]:
    prev_bars = []
    for pd in prev_dates:
        prev_bars.extend(engine.by_date_5m.get(pd, {}).get(sym, []))
    today_bars = engine.by_date_5m.get(target_date, {}).get(sym, [])

    print(f"\n--- {sym} ---")
    for b_idx in range(1, 15):
        time_m = 9 * 60 + 15 + b_idx * 5
        h = time_m // 60
        m = time_m % 60
        sess = prev_bars[-40:] + today_bars[:b_idx+1]
        closes = [float(b['close']) for b in sess]
        k9 = 2.0 / 10
        k21 = 2.0 / 22
        e9, e21 = closes[0], closes[0]
        for cl in closes:
            e9 = cl * k9 + e9 * (1 - k9)
            e21 = cl * k21 + e21 * (1 - k21)
        pv = sum(((float(b['high']) + float(b['low']) + float(b['close'])) / 3.0) * max(float(b.get('volume', 1)), 1.0) for b in today_bars[:b_idx+1])
        v = sum(max(float(b.get('volume', 1)), 1.0) for b in today_bars[:b_idx+1])
        vw = pv / v
        c = today_bars[b_idx]['close']
        o = today_bars[b_idx]['open']
        bull = c > vw and e9 >= e21
        bear = c < vw and e9 <= e21
        bias = "BULL" if bull else ("BEAR" if bear else "CHOP")
        print(f"{h:02d}:{m:02d} | Open={o} Close={c} VWAP={vw:.1f} EMA9={e9:.1f} EMA21={e21:.1f} | Bias={bias}")
