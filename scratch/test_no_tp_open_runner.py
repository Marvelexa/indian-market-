import json
import os
import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")
cache_dir = '.cache_indian_market_60d'
nifty_bars = json.load(open(f'{cache_dir}/NIFTY_5m.json'))

by_day = {}
for b in nifty_bars:
    d = datetime.datetime.fromtimestamp(b['timestamp']/1000.0, IST).strftime('%Y-%m-%d')
    by_day.setdefault(d, []).append(b)

sorted_days = sorted(by_day.keys())

# Test Strategy: NO FIXED TP (OPEN RUNNER) + TRAILING SL (EMA9 / Previous Bar Low)
print(f"Testing 60 Days with NO FIXED TP (OPEN RUNNER) on NIFTY...")

total_trades = 0
wins = 0
losses = 0
scratches = 0
total_pnl = 0.0
pnls = []

for d in sorted_days:
    bars = by_day[d]
    if len(bars) < 20:
        continue

    # Session VWAP computation
    cum_pv = 0.0
    cum_v = 0.0
    
    in_pos = False
    pos = None

    for idx in range(2, len(bars)):
        b = bars[idx]
        prev = bars[idx - 1]
        c = float(b['close'])
        o = float(b['open'])
        h = float(b['high'])
        l = float(b['low'])
        v = max(float(b.get('volume', 1)), 1.0)
        typ = (h + l + c) / 3.0
        cum_pv += typ * v
        cum_v += v
        vwap = cum_pv / cum_v

        # EMA 9 and EMA 21
        closes = [float(x['close']) for x in bars[:idx+1]]
        # Simple EMA calculation
        k9 = 2.0 / (9 + 1)
        ema9 = closes[0]
        for cl in closes[1:]:
            ema9 = (cl * k9) + (ema9 * (1 - k9))

        k21 = 2.0 / (21 + 1)
        ema21 = closes[0]
        for cl in closes[1:]:
            ema21 = (cl * k21) + (ema21 * (1 - k21))

        if not in_pos:
            # High-Conviction Institutional Trend Alignment:
            # 1. Bullish: Above VWAP, EMA9 > EMA21, Close > Open, pullback to EMA9
            if c > vwap and ema9 > ema21 and c > o and l <= ema9 * 1.001 and idx < len(bars) - 8:
                entry = c
                initial_sl = min(float(prev['low']), l, vwap) - 4.0 # Tight structural SL
                pos = {
                    'side': 'BUY',
                    'entry': entry,
                    'initial_sl': initial_sl,
                    'sl': initial_sl,
                    'highest': c,
                    'stage': 0, # 0: Initial, 1: Breakeven (+14 pts), 2: Trailing
                    'qty': 25 # 1 lot Nifty
                }
                in_pos = True
                continue

            # 2. Bearish: Below VWAP, EMA9 < EMA21, Close < Open, pullback to EMA9
            elif c < vwap and ema9 < ema21 and c < o and h >= ema9 * 0.999 and idx < len(bars) - 8:
                entry = c
                initial_sl = max(float(prev['high']), h, vwap) + 4.0
                pos = {
                    'side': 'SELL',
                    'entry': entry,
                    'initial_sl': initial_sl,
                    'sl': initial_sl,
                    'lowest': c,
                    'stage': 0,
                    'qty': 25
                }
                in_pos = True
                continue

        else:
            # IN POSITION: NO FIXED TP! PURE TRAILING STOP LOSS RUNNER!
            side = pos['side']
            entry = pos['entry']
            qty = pos['qty']

            exit_reason = None
            exit_price = c

            if side == 'BUY':
                pos['highest'] = max(pos['highest'], h)
                unrealized_gain = pos['highest'] - entry

                # 1. Quick Brokerage Shield at +18 pts (covers ₹350+):
                if pos['stage'] == 0 and unrealized_gain >= 18.0:
                    pos['stage'] = 1
                    pos['sl'] = entry + 14.0 # Lock +₹350 gross!

                # 2. Trailing SL behind previous bar low once in solid profit (+35 pts):
                if unrealized_gain >= 35.0:
                    pos['stage'] = 2
                    trail_candidate = max(float(prev['low']) - 2.0, ema9 - 3.0)
                    if trail_candidate > pos['sl']:
                        pos['sl'] = trail_candidate

                # Check SL hit
                if l <= pos['sl']:
                    exit_price = pos['sl']
                    exit_reason = "TRAILING_SL_HIT" if pos['stage'] >= 1 else "INITIAL_SL_HIT"

            else: # SELL
                pos['lowest'] = min(pos['lowest'], l)
                unrealized_gain = entry - pos['lowest']

                # 1. Quick Brokerage Shield at +18 pts:
                if pos['stage'] == 0 and unrealized_gain >= 18.0:
                    pos['stage'] = 1
                    pos['sl'] = entry - 14.0 # Lock +₹350 gross!

                # 2. Trailing SL behind previous bar high once in solid profit (+35 pts):
                if unrealized_gain >= 35.0:
                    pos['stage'] = 2
                    trail_candidate = min(float(prev['high']) + 2.0, ema9 + 3.0)
                    if trail_candidate < pos['sl']:
                        pos['sl'] = trail_candidate

                # Check SL hit
                if h >= pos['sl']:
                    exit_price = pos['sl']
                    exit_reason = "TRAILING_SL_HIT" if pos['stage'] >= 1 else "INITIAL_SL_HIT"

            # Auto square-off at end of day
            if not exit_reason and idx >= len(bars) - 2:
                exit_reason = "03:18_AUTO_SQUARE_OFF"
                exit_price = c

            if exit_reason:
                pt_pnl = (exit_price - entry) if side == 'BUY' else (entry - exit_price)
                pnl = pt_pnl * qty
                total_trades += 1
                total_pnl += pnl
                pnls.append(pnl)

                if pnl > 50:
                    wins += 1
                elif abs(pnl) <= 50:
                    scratches += 1
                else:
                    losses += 1

                in_pos = False
                pos = None

print("==================================================")
print(f"60-DAY TEST RESULTS: NO FIXED TP (OPEN RUNNER) + TRAILING SL")
print(f"Total Trades: {total_trades}")
print(f"Wins (Rode the Trend): {wins} ({wins/max(1,total_trades)*100:.1f}%)")
print(f"Breakeven / Scratches: {scratches} ({scratches/max(1,total_trades)*100:.1f}%)")
print(f"Losses: {losses} ({losses/max(1,total_trades)*100:.1f}%)")
win_rate = (wins + scratches) / max(1, total_trades) * 100
print(f"Green/Scratch Rate: {win_rate:.1f}%")
print(f"Net Realized PnL: ₹{total_pnl:,.2f}")
print("==================================================")
