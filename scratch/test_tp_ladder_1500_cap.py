import json
import os
import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")
cache_dir = '.cache_indian_market_60d'
symbols = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX', 'RELIANCE', 'HDFCBANK', 'ICICIBANK', 'SBIN', 'INFY', 'TCS', 'TATAMOTORS', 'AXISBANK', 'LT', 'BAJFINANCE']

# Load 60 days
by_day_data = {}
for sym in symbols:
    fpath = f"{cache_dir}/{sym}_5m.json"
    if not os.path.exists(fpath):
        continue
    bars = json.load(open(fpath))
    for b in bars:
        d = datetime.datetime.fromtimestamp(b['timestamp']/1000.0, IST).strftime('%Y-%m-%d')
        by_day_data.setdefault(d, {}).setdefault(sym, []).append(b)

sorted_days = sorted(by_day_data.keys())

# Test Strategy:
# 1. 1500 Loss Cap per trade / per day
# 2. TP 1: +₹300 (per-trade profit milestone) -> moves SL to Breakeven (+₹220-₹300 gross)
# 3. TP 2: +₹750 -> locks +₹500
# 4. TP 3: +₹1,500 -> locks +₹1,000
# 5. TP LAST: Open Runner trailing behind 5m candle

total_trades = 0
tp1_hits = 0
tp2_hits = 0
tp3_hits = 0
tplast_hits = 0
sl_hits = 0
total_pnl = 0.0

for d in sorted_days:
    d_data = by_day_data[d]
    nifty_bars = d_data.get('NIFTY', [])
    if len(nifty_bars) < 20:
        continue

    day_pnl = 0.0
    active_pos = []
    symbol_traded = {}

    for idx in range(3, min(74, len(nifty_bars))):
        if day_pnl <= -1500.0:
            # Circuit breaker: Daily loss cap reached!
            break

        # Master NIFTY trend bias
        n_c = float(nifty_bars[idx]['close'])
        n_sess = nifty_bars[:idx+1]
        n_pv = sum(((float(b['high']) + float(b['low']) + float(b['close'])) / 3.0) * max(float(b.get('volume', 1)), 1.0) for b in n_sess)
        n_v = sum(max(float(b.get('volume', 1)), 1.0) for b in n_sess)
        n_vwap = n_pv / n_v if n_v > 0 else n_c
        market_bull = n_c >= n_vwap

        # Evaluate active positions
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
            is_opt = pos['is_opt']

            # High / Low floating profit in Rupees
            pt_gain = (h - entry) if is_buy else (entry - l)
            curr_pt = (c - entry) if is_buy else (entry - c)
            rupee_gain = pt_gain * qty * (0.60 if is_opt else 1.0)

            # Milestones:
            # TP 1 at +₹300:
            if pos['stage'] == 0 and rupee_gain >= 300.0:
                pos['stage'] = 1
                pos['tp_hit'] = 1
                # Lock SL at Breakeven (+₹250 gross)
                buf_pts = (250.0 / (qty * 0.60)) if is_opt else (250.0 / qty)
                pos['sl'] = entry + buf_pts if is_buy else entry - buf_pts

            # TP 2 at +₹750:
            if pos['stage'] <= 1 and rupee_gain >= 750.0:
                pos['stage'] = 2
                pos['tp_hit'] = 2
                # Lock SL at +₹500 gross
                buf_pts = (500.0 / (qty * 0.60)) if is_opt else (500.0 / qty)
                pos['sl'] = entry + buf_pts if is_buy else entry - buf_pts

            # TP 3 at +₹1,500:
            if pos['stage'] <= 2 and rupee_gain >= 1500.0:
                pos['stage'] = 3
                pos['tp_hit'] = 3
                # Lock SL at +₹1,000 gross
                buf_pts = (1000.0 / (qty * 0.60)) if is_opt else (1000.0 / qty)
                pos['sl'] = entry + buf_pts if is_buy else entry - buf_pts

            # TP LAST: Dynamic candle trailing SL
            if pos['stage'] >= 3:
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
                stage = pos['stage']
                exit_r = f"TP_{stage}_EXIT" if stage >= 1 else "STOP_LOSS_HIT"
            elif not is_buy and h >= pos['sl']:
                exit_p = pos['sl']
                stage = pos['stage']
                exit_r = f"TP_{stage}_EXIT" if stage >= 1 else "STOP_LOSS_HIT"
            elif idx >= min(72, len(bars) - 2):
                exit_r = "03:18_AUTO_SQUARE_OFF"
                exit_p = c

            if exit_r:
                pnl = (exit_p - entry) * qty if is_buy else (entry - exit_p) * qty
                if is_opt:
                    pnl *= 0.60
                
                # ₹1,500 Loss Cap per trade!
                pnl = max(-1500.0, pnl)

                total_trades += 1
                total_pnl += pnl
                day_pnl += pnl

                if "TP_1" in exit_r:
                    tp1_hits += 1
                elif "TP_2" in exit_r:
                    tp2_hits += 1
                elif "TP_3" in exit_r or "LAST" in exit_r:
                    tp3_hits += 1
                elif pnl > 0:
                    tplast_hits += 1
                else:
                    sl_hits += 1
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

                past5 = bars[max(0, idx-5):idx+1]
                swing_low5 = min(float(b['low']) for b in past5)
                swing_high5 = max(float(b['high']) for b in past5)

                if sym == 'NIFTY':
                    sl_pts_buy = max(60.0, close_p - swing_low5 + 12.0)
                    sl_pts_sell = max(60.0, swing_high5 - close_p + 12.0)
                    lot = 25
                elif sym == 'BANKNIFTY':
                    sl_pts_buy = max(200.0, close_p - swing_low5 + 35.0)
                    sl_pts_sell = max(200.0, swing_high5 - close_p + 35.0)
                    lot = 15
                elif sym == 'SENSEX':
                    sl_pts_buy = max(220.0, close_p - swing_low5 + 40.0)
                    sl_pts_sell = max(220.0, swing_high5 - close_p + 40.0)
                    lot = 10
                elif sym == 'FINNIFTY':
                    sl_pts_buy = max(70.0, close_p - swing_low5 + 15.0)
                    sl_pts_sell = max(70.0, swing_high5 - close_p + 15.0)
                    lot = 40
                else:
                    sl_pts_buy = max(close_p * 0.0095, (close_p - swing_low5) + (close_p * 0.0025))
                    sl_pts_sell = max(close_p * 0.0095, (swing_high5 - close_p) + (close_p * 0.0025))
                    # ₹1,500 max cap position sizing:
                    lot = max(10, min(100, int(1500.0 / sl_pts_buy)))

                # BUY ENTRY
                if market_bull and close_p > vwap and ema9 > ema21 and close_p > open_p and low_p <= ema9 * 1.002:
                    sl_price = round(close_p - sl_pts_buy, 2)
                    active_pos.append({
                        'symbol': sym,
                        'side': 'BUY',
                        'entry': close_p,
                        'sl': sl_price,
                        'stage': 0,
                        'tp_hit': 0,
                        'qty': lot,
                        'is_opt': is_opt
                    })
                    symbol_traded[sym] = 1

                # SELL ENTRY
                elif not market_bull and close_p < vwap and ema9 < ema21 and close_p < open_p and high_p >= ema9 * 0.998:
                    sl_price = round(close_p + sl_pts_sell, 2)
                    active_pos.append({
                        'symbol': sym,
                        'side': 'SELL',
                        'entry': close_p,
                        'sl': sl_price,
                        'stage': 0,
                        'tp_hit': 0,
                        'qty': lot,
                        'is_opt': is_opt
                    })
                    symbol_traded[sym] = 1

print("==================================================")
print("60-DAY MULTI-ASSET RESULTS: ₹1500 LOSS CAP + TP 1/2/3/LAST LADDER")
print(f"Total Trades: {total_trades}")
print(f"TP 1 (+₹300) Exits: {tp1_hits}")
print(f"TP 2 (+₹750) Exits: {tp2_hits}")
print(f"TP 3 / LAST (+₹1,500+) Exits: {tp3_hits + tplast_hits}")
print(f"Stop Loss Hits: {sl_hits}")
win_rate = (total_trades - sl_hits) / max(1, total_trades) * 100
print(f"Win Rate: {win_rate:.1f}%")
print(f"Net Realized PnL: +₹{total_pnl:,.2f}")
print("==================================================")
