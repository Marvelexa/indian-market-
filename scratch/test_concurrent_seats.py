import json, os, datetime, pytz

IST = pytz.timezone('Asia/Kolkata')
cache_dir = '.cache_indian_market_60d'
symbols = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX', 'RELIANCE', 'HDFCBANK', 'ICICIBANK', 'SBIN', 'INFY', 'TCS', 'TATAMOTORS', 'AXISBANK', 'LT', 'BAJFINANCE']

by_day_data = {}
for sym in symbols:
    fpath = f'{cache_dir}/{sym}_5m.json'
    if not os.path.exists(fpath): continue
    bars = json.load(open(fpath))
    for b in bars:
        d = datetime.datetime.fromtimestamp(b['timestamp']/1000.0, IST).strftime('%Y-%m-%d')
        by_day_data.setdefault(d, {}).setdefault(sym, []).append(b)

sorted_days = sorted(by_day_data.keys())

def test_max_concurrent(max_seats=2, daily_stop=-2000):
    total_pnl = 0.0
    wins = 0
    trades = 0
    green_days = 0
    red_days = 0

    for d in sorted_days:
        d_data = by_day_data[d]
        nifty_bars = d_data.get('NIFTY', [])
        if len(nifty_bars) < 20: continue

        day_pnl = 0.0
        active_pos = []
        symbol_traded = {}

        for idx in range(3, min(74, len(nifty_bars))):
            if day_pnl <= daily_stop: break

            n_c = float(nifty_bars[idx]['close'])
            n_sess = nifty_bars[:idx+1]
            n_pv = sum(((float(b['high']) + float(b['low']) + float(b['close'])) / 3.0) * max(float(b.get('volume', 1)), 1.0) for b in n_sess)
            n_v = sum(max(float(b.get('volume', 1)), 1.0) for b in n_sess)
            n_vwap = n_pv / n_v if n_v > 0 else n_c
            market_bull = n_c >= n_vwap

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
                entry = pos['entry']
                qty = pos['qty']
                is_opt = pos['is_opt']
                mult = qty * (0.60 if is_opt else 1.0)

                best_gain = ((h - entry) if pos['side'] == 'BUY' else (entry - l)) * mult

                # TP 1 (1000) -> Lock 700
                if pos['stage'] == 0 and best_gain >= 1000.0:
                    pos['stage'] = 1
                    buf_pts = 700.0 / mult
                    pos['sl'] = entry + buf_pts if pos['side'] == 'BUY' else entry - buf_pts

                # TP 2 (1300) -> Lock 1000
                if pos['stage'] <= 1 and best_gain >= 1300.0:
                    pos['stage'] = 2
                    buf_pts = 1000.0 / mult
                    new_sl = entry + buf_pts if pos['side'] == 'BUY' else entry - buf_pts
                    if (pos['side'] == 'BUY' and new_sl > pos['sl']) or (pos['side'] == 'SELL' and new_sl < pos['sl']):
                        pos['sl'] = new_sl

                # TP 3 (1500) -> Full Target Exit
                if best_gain >= 1500.0:
                    pnl = 1500.0
                    total_pnl += pnl
                    day_pnl += pnl
                    trades += 1
                    wins += 1
                    continue

                # SL hit
                sl_hit = (l <= pos['sl']) if pos['side'] == 'BUY' else (h >= pos['sl'])
                if sl_hit:
                    exit_price = pos['sl']
                    trade_pnl = ((exit_price - entry) if pos['side'] == 'BUY' else (entry - exit_price)) * mult
                    if trade_pnl < -900.0: trade_pnl = -900.0
                    total_pnl += trade_pnl
                    day_pnl += trade_pnl
                    trades += 1
                    if trade_pnl > 0: wins += 1
                    continue

                rem.append(pos)
            active_pos = rem

            # Entry
            if len(active_pos) >= max_seats: continue
            for sym in symbols:
                if len(active_pos) >= max_seats: break
                if any(p['symbol'] == sym for p in active_pos): continue
                if symbol_traded.get(sym, 0) >= 1: continue

                bars = d_data.get(sym, [])
                if idx < 3 or idx >= len(bars) - 5: continue
                c_bar = bars[idx]
                close_p = float(c_bar['close'])
                open_p = float(c_bar['open'])
                low_p = float(c_bar['low'])

                session_bars = bars[:idx+1]
                cum_pv = sum(((float(b['high']) + float(b['low']) + float(b['close'])) / 3.0) * max(float(b.get('volume', 1)), 1.0) for b in session_bars)
                cum_v = sum(max(float(b.get('volume', 1)), 1.0) for b in session_bars)
                vwap = cum_pv / cum_v if cum_v > 0 else close_p

                closes = [float(b['close']) for b in session_bars]
                k9 = 2.0 / 10
                k21 = 2.0 / 22
                ema9 = closes[0]
                ema21 = closes[0]
                for cl in closes:
                    ema9 = cl * k9 + ema9 * (1 - k9)
                    ema21 = cl * k21 + ema21 * (1 - k21)

                is_opt = sym in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX']
                past5 = bars[max(0, idx-5):idx+1]
                swing_low5 = min(float(b['low']) for b in past5)

                if sym == 'NIFTY':
                    sl_pts = max(45.0, close_p - swing_low5 + 10.0)
                    lot = 25
                elif sym == 'BANKNIFTY':
                    sl_pts = max(90.0, close_p - swing_low5 + 15.0)
                    lot = 15
                elif sym == 'SENSEX':
                    sl_pts = max(140.0, close_p - swing_low5 + 20.0)
                    lot = 10
                elif sym == 'FINNIFTY':
                    sl_pts = max(45.0, close_p - swing_low5 + 10.0)
                    lot = 25
                else:
                    sl_pts = max(close_p * 0.008, (close_p - swing_low5) + (close_p * 0.002))
                    lot = max(10, min(100, int(900.0 / sl_pts)))

                if market_bull and close_p > vwap and ema9 > ema21 and close_p > open_p and low_p <= ema9 * 1.002:
                    active_pos.append({'symbol': sym, 'side': 'BUY', 'entry': close_p, 'sl': close_p - sl_pts, 'stage': 0, 'qty': lot, 'is_opt': is_opt})
                    symbol_traded[sym] = 1

        if day_pnl > 0: green_days += 1
        elif day_pnl < 0: red_days += 1

    win_rate = (wins / trades * 100) if trades > 0 else 0
    print(f"Seats: {max_seats} | DailyStop: {daily_stop} => Trades: {trades}, Wins: {wins} ({win_rate:.1f}%), GreenDays: {green_days}, Net PnL: Rs. {total_pnl:,.2f}")

for seats in [2, 3, 4, 6]:
    for stop in [-1500, -2000, -2500]:
        test_max_concurrent(seats, stop)
