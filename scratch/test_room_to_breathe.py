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

def run_backtest(tp1_target, tp2_target, tp3_target, be_trigger, trail_dist_pts):
    total_trades = 0
    wins = 0
    total_pnl = 0.0
    big_winners = 0

    for d in sorted_days:
        d_data = by_day_data[d]
        nifty_bars = d_data.get('NIFTY', [])
        if len(nifty_bars) < 20: continue

        day_pnl = 0.0
        active_pos = []
        symbol_traded = {}

        for idx in range(3, min(74, len(nifty_bars))):
            if day_pnl <= -1500.0: break

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
                c = float(b['close'])
                is_buy = pos['side'] == 'BUY'
                entry = pos['entry']
                qty = pos['qty']
                is_opt = pos['is_opt']

                # Floating PnL
                pt_gain = (h - entry) if is_buy else (entry - l)
                rupee_gain = pt_gain * qty * (0.60 if is_opt else 1.0)

                # Move to Breakeven ONLY when trade has substantial cushion (e.g. at be_trigger)
                # And give trailing room!
                if pos['stage'] == 0 and rupee_gain >= be_trigger:
                    pos['stage'] = 1
                    # Set SL to Entry (exact breakeven, or entry + small buffer)
                    pos['sl'] = entry if is_buy else entry

                # TP 2 milestone
                if pos['stage'] <= 1 and rupee_gain >= tp2_target:
                    pos['stage'] = 2
                    # Lock 50% of gain
                    locked_pts = (tp1_target / (qty * 0.60 if is_opt else qty))
                    pos['sl'] = entry + locked_pts if is_buy else entry - locked_pts

                # TP 3 milestone
                if pos['stage'] <= 2 and rupee_gain >= tp3_target:
                    pos['stage'] = 3
                    locked_pts = (tp2_target / (qty * 0.60 if is_opt else qty))
                    pos['sl'] = entry + locked_pts if is_buy else entry - locked_pts

                # TP LAST runner: Trail behind 5m candle low/high with generous room
                if pos['stage'] >= 3:
                    prev_b = bars[idx - 1]
                    if is_buy:
                        trail = float(prev_b['low'])
                        if trail > pos['sl']: pos['sl'] = trail
                    else:
                        trail = float(prev_b['high'])
                        if trail < pos['sl']: pos['sl'] = trail

                exit_r = None
                exit_p = c

                # Check SL
                if is_buy and l <= pos['sl']:
                    exit_p = pos['sl']
                    exit_r = 'SL_EXIT'
                elif not is_buy and h >= pos['sl']:
                    exit_p = pos['sl']
                    exit_r = 'SL_EXIT'
                elif idx >= min(72, len(bars) - 2):
                    exit_r = 'EOD_EXIT'

                if exit_r:
                    pt_move = (exit_p - entry) if is_buy else (entry - exit_p)
                    pnl = pt_move * qty * (0.60 if is_opt else 1.0)
                    if pnl < -1500.0: pnl = -1500.0
                    day_pnl += pnl
                    total_pnl += pnl
                    total_trades += 1
                    if pnl > 0: wins += 1
                    if pnl >= 1500.0: big_winners += 1
                else:
                    rem.append(pos)
            active_pos = rem

            # Entries
            if len(active_pos) < 6 and idx < len(nifty_bars) - 10:
                for sym in symbols:
                    if len(active_pos) >= 6: break
                    if any(p['symbol'] == sym for p in active_pos) or symbol_traded.get(sym, 0) >= 1: continue
                    bars = d_data.get(sym, [])
                    if idx >= len(bars): continue
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
                    k9, k21 = 2.0/10, 2.0/22
                    ema9, ema21 = closes_list[0], closes_list[0]
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
                        sl_pts_buy = max(160.0, close_p - swing_low5 + 30.0)
                        sl_pts_sell = max(160.0, swing_high5 - close_p + 30.0)
                        lot = 15
                    elif sym == 'SENSEX':
                        sl_pts_buy = max(220.0, close_p - swing_low5 + 40.0)
                        sl_pts_sell = max(220.0, swing_high5 - close_p + 40.0)
                        lot = 10
                    elif sym == 'FINNIFTY':
                        sl_pts_buy = max(70.0, close_p - swing_low5 + 15.0)
                        sl_pts_sell = max(70.0, swing_high5 - close_p + 15.0)
                        lot = 25
                    else:
                        sl_pts_buy = max(close_p * 0.0095, (close_p - swing_low5) + (close_p * 0.0025))
                        sl_pts_sell = max(close_p * 0.0095, (swing_high5 - close_p) + (close_p * 0.0025))
                        lot = max(10, min(100, int(1500.0 / sl_pts_buy)))

                    if market_bull and close_p > vwap and ema9 > ema21 and close_p > open_p and low_p <= ema9 * 1.002:
                        active_pos.append({'symbol': sym, 'side': 'BUY', 'entry': close_p, 'sl': close_p - sl_pts_buy, 'stage': 0, 'qty': lot, 'is_opt': is_opt})
                        symbol_traded[sym] = 1
                    elif not market_bull and close_p < vwap and ema9 < ema21 and close_p < open_p and high_p >= ema9 * 0.998:
                        active_pos.append({'symbol': sym, 'side': 'SELL', 'entry': close_p, 'sl': close_p + sl_pts_sell, 'stage': 0, 'qty': lot, 'is_opt': is_opt})
                        symbol_traded[sym] = 1

    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    return total_trades, wins, win_rate, total_pnl, big_winners

print("Testing different breathing room thresholds...")
# Test 1: Current model (Choked at 300)
# Test 2: Breakeven at 1000, TP2 at 2500, TP3 at 5000
# Test 3: Breakeven at 1500, TP2 at 3500, TP3 at 7000
for name, be, t2, t3 in [
    ("Tight (300 BE / 750 / 1500)", 300, 750, 1500),
    ("Medium Breathing Room (800 BE / 2000 / 4000)", 800, 2000, 4000),
    ("Institutional 20K Target (1500 BE / 3500 / 7000)", 1500, 3500, 7000),
    ("High Potential Runner (2000 BE / 5000 / 10000)", 2000, 5000, 10000)
]:
    t, w, wr, pnl, big = run_backtest(be, t2, t3, be, 0)
    print(f"[{name}]")
    print(f"  Trades: {t}, Wins: {w}, WinRate: {wr:.1f}%, Net PnL: ₹{pnl:,.2f}, Big Winners (>=₹1.5K): {big}")
