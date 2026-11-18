import json
import os
import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")
cache_dir = '.cache_indian_market_60d'
nifty_bars = json.load(open(f'{cache_dir}/NIFTY_5m.json'))

# Group by day
by_day = {}
for b in nifty_bars:
    d = datetime.datetime.fromtimestamp(b['timestamp']/1000.0, IST).strftime('%Y-%m-%d')
    by_day.setdefault(d, []).append(b)

sorted_days = sorted(by_day.keys())

total_trades = 0
tp_hits = 0
lock_hits = 0
scratch_hits = 0
sl_hits = 0
total_pnl = 0.0

for d in sorted_days:
    bars = by_day[d]
    if len(bars) < 25:
        continue
    
    # Opening Range High / Low (first 2 bars: 09:15-09:25)
    orh = max(b['high'] for b in bars[:2])
    orl = min(b['low'] for b in bars[:2])

    in_pos = False
    pos = None

    for idx in range(2, len(bars)):
        b = bars[idx]
        prev = bars[idx - 1]
        c_p = float(b['close'])
        o_p = float(b['open'])
        h_p = float(b['high'])
        l_p = float(b['low'])

        # Compute 14-period ATR
        recent_bars = bars[max(0, idx - 14):idx + 1]
        trs = [max(float(rb['high']) - float(rb['low']), abs(float(rb['high']) - float(bars[i-1]['close'] if i > 0 else float(rb['open'])))) for i, rb in enumerate(recent_bars)]
        atr = sum(trs) / len(trs) if trs else 30.0
        atr = max(15.0, min(60.0, atr))

        if not in_pos:
            # Check Buy Signal (Breakout or EMA pull)
            if c_p > o_p and c_p > prev['close'] and (c_p - l_p) > (h_p - c_p) * 1.3:
                # Long
                entry = c_p
                sl_dist = max(atr * 0.9, 25.0) # Tight institutional SL (~30 pts)
                
                # Candlestick Study for Smart TP
                # Check nearest resistance walls: ORH, Session High, prior high wicks
                sess_high = max(float(sb['high']) for sb in bars[:idx+1])
                walls = []
                if orh > entry + 15:
                    walls.append(orh)
                if sess_high > entry + 15:
                    walls.append(sess_high)
                for pb in bars[max(0, idx-20):idx]:
                    if float(pb['high']) > entry + 15:
                        walls.append(float(pb['high']))
                
                if walls:
                    wall = min(walls) # Nearest overhead wall
                    buf = max(4.0, wall * 0.0003)
                    tp = wall - buf
                else:
                    tp = entry + atr * 1.65 # Realistic impulse target
                
                # Position Sizing for ₹1L capital (Nifty 1 lot = 25 qty)
                qty = 25
                target_pts = tp - entry
                if target_pts < 18.0:
                    tp = entry + max(atr * 1.5, 28.0) # Minimum viable target
                    target_pts = tp - entry

                pos = {
                    'entry': entry,
                    'sl': entry - sl_dist,
                    'tp': tp,
                    'initial_tp': tp,
                    'qty': qty,
                    'stage': 0, # 0: Initial, 1: Brokerage-Shielded Scratch, 2: 65% Profit Lock
                    'target_pts': target_pts
                }
                in_pos = True
                continue

        else:
            # In position: evaluate against bar high and low
            entry = pos['entry']
            tp = pos['tp']
            sl = pos['sl']
            qty = pos['qty']
            target_pts = pos['target_pts']

            # High reached in this bar
            max_p = h_p
            min_p = l_p
            curr_p = c_p

            runway_covered = max_p - entry
            progress_pct = (runway_covered / target_pts * 100.0) if target_pts > 0 else 0.0

            # 1. Brokerage-Shielded Breakeven (at 38% progress):
            # Guarantee at least +₹350 gross (covers all brokerage + STT + taxes)
            if pos['stage'] == 0 and progress_pct >= 38.0:
                pos['stage'] = 1
                pos['sl'] = round(entry + (350.0 / qty), 2) # Entry + 14 pts

            # 2. Smart Institutional Profit Lock (at 65% progress):
            # Lock in 65% of target profit
            if pos['stage'] <= 1 and progress_pct >= 65.0:
                pos['stage'] = 2
                pos['sl'] = round(entry + (target_pts * 0.65), 2)

            # 3. Check Candle Exhaustion Reversal (if >= 70% progress and bar leaves upper wick)
            upper_wick = h_p - max(o_p, c_p)
            bar_rng = max(h_p - l_p, 0.1)
            is_exhaustion = (progress_pct >= 70.0) and (upper_wick / bar_rng >= 0.40)

            # Check exits
            exit_reason = None
            exit_p = curr_p

            if max_p >= tp:
                exit_reason = "SMART_TP_HIT"
                exit_p = tp
            elif is_exhaustion:
                exit_reason = "SMART_TP_EXHAUSTION_LOCK"
                exit_p = c_p
            elif min_p <= pos['sl']:
                exit_p = pos['sl']
                if pos['stage'] == 2:
                    exit_reason = "PROFIT_LOCKED_EXIT"
                elif pos['stage'] == 1:
                    exit_reason = "BROKERAGE_SHIELDED_SCRATCH"
                else:
                    exit_reason = "STOP_LOSS_HIT"
            elif idx >= len(bars) - 2: # 03:18 PM Square-off
                exit_reason = "AUTO_SQUARE_OFF"
                exit_p = c_p

            if exit_reason:
                pnl = (exit_p - entry) * qty
                total_trades += 1
                total_pnl += pnl
                if exit_reason in ["SMART_TP_HIT", "SMART_TP_EXHAUSTION_LOCK"]:
                    tp_hits += 1
                elif exit_reason == "PROFIT_LOCKED_EXIT":
                    lock_hits += 1
                elif exit_reason == "BROKERAGE_SHIELDED_SCRATCH":
                    scratch_hits += 1
                elif exit_reason == "STOP_LOSS_HIT":
                    sl_hits += 1

                in_pos = False
                pos = None

print("==================================================")
print(f"60-DAY TEST RESULTS WITH SMART CANDLE TP & BROKERAGE SHIELD:")
print(f"Total Trades: {total_trades}")
print(f"Smart TP Hits: {tp_hits} ({tp_hits/total_trades*100:.1f}%)")
print(f"65% Profit Lock Hits: {lock_hits} ({lock_hits/total_trades*100:.1f}%)")
print(f"Brokerage-Shielded Scratch Hits (+₹350 Gross): {scratch_hits} ({scratch_hits/total_trades*100:.1f}%)")
print(f"Stop Loss Hits: {sl_hits} ({sl_hits/total_trades*100:.1f}%)")
win_rate = (tp_hits + lock_hits + scratch_hits) / total_trades * 100
print(f"Overall Green / Non-Losing Rate: {win_rate:.1f}%")
print(f"Net Realized PnL: ₹{total_pnl:,.2f}")
print("==================================================")
