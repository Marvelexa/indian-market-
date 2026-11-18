import json
import os
import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")
cache_dir = '.cache_indian_market_60d'

# 14 Whitelist symbols
symbols = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX', 'RELIANCE', 'HDFCBANK', 'ICICIBANK', 'SBIN', 'INFY', 'TCS', 'TATAMOTORS', 'AXISBANK', 'LT', 'BAJFINANCE']
day_target = "2026-11-04"

print(f"--- Simulating Day {day_target} with PROPER WIDE STRUCTURAL SL (Breathing Room) ---")

d_data = {}
for sym in symbols:
    fpath = f"{cache_dir}/{sym}_5m.json"
    if not os.path.exists(fpath):
        continue
    bars = json.load(open(fpath))
    day_bars = [b for b in bars if datetime.datetime.fromtimestamp(b['timestamp']/1000.0, IST).strftime('%Y-%m-%d') == day_target]
    if day_bars:
        d_data[sym] = day_bars

nifty_bars = d_data.get('NIFTY', [])
print(f"Loaded {len(d_data)} symbols on {day_target}. Total bars: {len(nifty_bars)}")

active_pos = []
closed = []
symbol_traded = {}

for idx in range(3, min(74, len(nifty_bars))):
    # Master NIFTY bias
    n_c = float(nifty_bars[idx]['close'])
    n_pv = sum(((float(b['high']) + float(b['low']) + float(b['close'])) / 3.0) * max(float(b.get('volume', 1)), 1.0) for b in nifty_bars[:idx+1])
    n_v = sum(max(float(b.get('volume', 1)), 1.0) for b in nifty_bars[:idx+1])
    n_vwap = n_pv / n_v if n_v > 0 else n_c
    market_bull = n_c >= n_vwap

    # Check active positions
    rem = []
    for pos in active_pos:
        sym = pos['symbol']
        bars = d_data.get(sym, [])
        if idx >= len(bars):
            rem.append(pos)
            continue
        b = bars[idx]
        h = float(b['high'])
        l = float(b['low'])
        c = float(b['close'])
        is_buy = pos['side'] == 'BUY'
        entry = pos['entry']
        qty = pos['qty']

        # Gain
        gain = (h - entry) if is_buy else (entry - l)
        gain_pct = (gain / entry) * 100.0

        # 1. Quick Brokerage Shield at +0.40% gain (locks +₹220/+₹350)
        if pos['stage'] == 0 and gain_pct >= 0.40:
            pos['stage'] = 1
            buffer_pts = (350.0 / (qty * 0.60)) if pos['is_opt'] else (250.0 / qty)
            pos['sl'] = entry + buffer_pts if is_buy else entry - buffer_pts

        # 2. Dynamic Trailing SL at +0.80% gain: trail behind previous 5m candle low/high
        if gain_pct >= 0.80:
            pos['stage'] = 2
            prev_b = bars[idx - 1]
            if is_buy:
                trail = float(prev_b['low']) - (entry * 0.001)
                if trail > pos['sl']:
                    pos['sl'] = trail
            else:
                trail = float(prev_b['high']) + (entry * 0.001)
                if trail < pos['sl']:
                    pos['sl'] = trail

        exit_r = None
        exit_p = c
        if is_buy and l <= pos['sl']:
            exit_p = pos['sl']
            exit_r = "TRAILING_RUNNER_EXIT" if pos['stage'] >= 2 else ("BROKERAGE_SHIELDED_SCRATCH" if pos['stage'] == 1 else "STRUCTURAL_SL_HIT")
        elif not is_buy and h >= pos['sl']:
            exit_p = pos['sl']
            exit_r = "TRAILING_RUNNER_EXIT" if pos['stage'] >= 2 else ("BROKERAGE_SHIELDED_SCRATCH" if pos['stage'] == 1 else "STRUCTURAL_SL_HIT")
        elif idx >= min(72, len(bars) - 2):
            exit_r = "03:18_AUTO_SQUARE_OFF"
            exit_p = c

        if exit_r:
            pnl = (exit_p - entry) * qty if is_buy else (entry - exit_p) * qty
            if pos['is_opt']:
                pnl *= 0.60
            closed.append({
                'symbol': sym,
                'side': pos['side'],
                'entry': entry,
                'exit': round(exit_p, 2),
                'pnl': round(pnl, 2),
                'reason': exit_r
            })
        else:
            rem.append(pos)
    active_pos = rem

    # Open new trades (Max 6 concurrent)
    if len(active_pos) < 6 and idx < len(nifty_bars) - 10:
        for sym in symbols:
            if len(active_pos) >= 6:
                break
            if any(p['symbol'] == sym for p in active_pos) or symbol_traded.get(sym, 0) >= 1:
                continue
            bars = d_data.get(sym, [])
            if idx >= len(bars):
                continue
            c_b = bars[idx]
            close_p = float(c_b['close'])
            open_p = float(c_b['open'])
            high_p = float(c_b['high'])
            low_p = float(c_b['low'])

            sess_bars = bars[:idx+1]
            cum_pv = sum(((float(b['high']) + float(b['low']) + float(b['close'])) / 3.0) * max(float(b.get('volume', 1)), 1.0) for b in sess_bars)
            cum_v = sum(max(float(b.get('volume', 1)), 1.0) for b in sess_bars)
            vwap = cum_pv / cum_v if cum_v > 0 else close_p

            closes_list = [float(b['close']) for b in sess_bars]
            k9 = 2.0 / 10
            k21 = 2.0 / 22
            ema9 = closes_list[0]
            ema21 = closes_list[0]
            for cl in closes_list:
                ema9 = cl * k9 + ema9 * (1 - k9)
                ema21 = cl * k21 + ema21 * (1 - k21)

            is_opt = sym in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX']

            # Proper Volatility / Structural SL Calculation:
            # Look at past 5 bars swing low/high
            past5 = bars[max(0, idx-5):idx+1]
            swing_low5 = min(float(b['low']) for b in past5)
            swing_high5 = max(float(b['high']) for b in past5)

            # Volatility SL distances (in points / rupees):
            # Give real breathing room!
            if sym == 'NIFTY':
                sl_pts = max(60.0, close_p - swing_low5 + 10.0)
                lot = 25
            elif sym == 'BANKNIFTY':
                sl_pts = max(200.0, close_p - swing_low5 + 30.0)
                lot = 15
            elif sym == 'SENSEX':
                sl_pts = max(220.0, close_p - swing_low5 + 35.0)
                lot = 10
            elif sym == 'FINNIFTY':
                sl_pts = max(70.0, close_p - swing_low5 + 12.0)
                lot = 40
            else:
                # Equities: 0.90% to 1.30% real breathing room
                sl_pts = max(close_p * 0.0095, close_p - swing_low5 + (close_p * 0.002))
                # Dynamic position sizing for ₹500 risk:
                lot = max(10, min(100, int(500.0 / sl_pts)))

            # BUY ENTRY
            if market_bull and close_p > vwap and ema9 > ema21 and close_p > open_p and low_p <= ema9 * 1.002:
                sl_price = round(close_p - sl_pts, 2)
                active_pos.append({
                    'symbol': sym,
                    'side': 'BUY',
                    'entry': close_p,
                    'sl': sl_price,
                    'stage': 0,
                    'qty': lot,
                    'is_opt': is_opt
                })
                symbol_traded[sym] = 1

            # SELL ENTRY
            elif not market_bull and close_p < vwap and ema9 < ema21 and close_p < open_p and high_p >= ema9 * 0.998:
                if sym == 'NIFTY':
                    sl_pts_sell = max(60.0, swing_high5 - close_p + 10.0)
                elif sym == 'BANKNIFTY':
                    sl_pts_sell = max(200.0, swing_high5 - close_p + 30.0)
                elif sym == 'SENSEX':
                    sl_pts_sell = max(220.0, swing_high5 - close_p + 35.0)
                elif sym == 'FINNIFTY':
                    sl_pts_sell = max(70.0, swing_high5 - close_p + 12.0)
                else:
                    sl_pts_sell = max(close_p * 0.0095, swing_high5 - close_p + (close_p * 0.002))
                    lot = max(10, min(100, int(500.0 / sl_pts_sell)))

                sl_price = round(close_p + sl_pts_sell, 2)
                active_pos.append({
                    'symbol': sym,
                    'side': 'SELL',
                    'entry': close_p,
                    'sl': sl_price,
                    'stage': 0,
                    'qty': lot,
                    'is_opt': is_opt
                })
                symbol_traded[sym] = 1

print("\n==================================================")
print(f"Results for {day_target} with PROPER WIDE SL:")
print(f"Total Trades: {len(closed)}")
tot_pnl = sum(c['pnl'] for c in closed)
print(f"Net Realized PnL: ₹{tot_pnl:,.2f}")
for c in closed:
    print(f"  {c['symbol']} {c['side']} Entry: ₹{c['entry']} -> Exit: ₹{c['exit']} | PnL: ₹{c['pnl']} ({c['reason']})")
print("==================================================")
