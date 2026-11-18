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

def test_single_day(target_date, tp1=1000, lock1=600, tp2=1300, lock2=1000, tp3=1500, max_sl_cap=1000):
    d_data = by_day_data.get(target_date, {})
    nifty_bars = d_data.get('NIFTY', [])
    if not nifty_bars:
        print(f"No data for {target_date}")
        return

    day_pnl = 0.0
    active_pos = []
    symbol_traded = {}
    ledger = []

    for idx in range(3, min(74, len(nifty_bars))):
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
            mult = qty * (0.60 if is_opt else 1.0)

            best_gain = ((h - entry) if is_buy else (entry - l)) * mult
            worst_gain = ((l - entry) if is_buy else (entry - h)) * mult

            # Stage 1: TP 1 (1000)
            if pos['stage'] == 0 and best_gain >= tp1:
                pos['stage'] = 1
                buf_pts = lock1 / mult
                pos['sl'] = entry + buf_pts if is_buy else entry - buf_pts

            # Stage 2: TP 2 (1300)
            if pos['stage'] <= 1 and best_gain >= tp2:
                pos['stage'] = 2
                buf_pts = lock2 / mult
                new_sl = entry + buf_pts if is_buy else entry - buf_pts
                if (is_buy and new_sl > pos['sl']) or (not is_buy and new_sl < pos['sl']):
                    pos['sl'] = new_sl

            # Stage 3: TP 3 (1500) -> Target hit, exit
            if best_gain >= tp3:
                pnl = tp3
                day_pnl += pnl
                ledger.append({'symbol': sym, 'pnl': pnl, 'reason': '🎯 TP 3 (+₹1,500 TARGET HIT)'})
                continue

            # SL hit
            sl_hit = (l <= pos['sl']) if is_buy else (h >= pos['sl'])
            if sl_hit:
                exit_price = pos['sl']
                pnl = ((exit_price - entry) if is_buy else (entry - exit_price)) * mult
                if pnl < -max_sl_cap:
                    pnl = -max_sl_cap
                day_pnl += pnl
                reason = f"🎯 TP 2 LOCKED (+₹{pnl:.0f})" if pos['stage'] == 2 else (f"🎯 TP 1 LOCKED (+₹{pnl:.0f})" if pos['stage'] == 1 else f"🛑 STOP LOSS (-₹{abs(pnl):.0f})")
                ledger.append({'symbol': sym, 'pnl': pnl, 'reason': reason})
                continue

            rem.append(pos)
        active_pos = rem

        # Entry logic
        if len(active_pos) >= 6: continue
        for sym in symbols:
            if len(active_pos) >= 6: break
            if any(p['symbol'] == sym for p in active_pos): continue
            if symbol_traded.get(sym, 0) >= 1: continue

            bars = d_data.get(sym, [])
            if idx < 3 or idx >= len(bars) - 5: continue
            c_bar = bars[idx]
            close_p = float(c_bar['close'])
            open_p = float(c_bar['open'])
            high_p = float(c_bar['high'])
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
                sl_pts = max(40.0, close_p - swing_low5 + 10.0)
                lot = 25
            elif sym == 'BANKNIFTY':
                sl_pts = max(100.0, close_p - swing_low5 + 20.0)
                lot = 15
            elif sym == 'SENSEX':
                sl_pts = max(150.0, close_p - swing_low5 + 30.0)
                lot = 10
            elif sym == 'FINNIFTY':
                sl_pts = max(50.0, close_p - swing_low5 + 10.0)
                lot = 25
            else:
                sl_pts = max(close_p * 0.008, (close_p - swing_low5) + (close_p * 0.002))
                lot = max(10, min(100, int(max_sl_cap / sl_pts)))

            if market_bull and close_p > vwap and ema9 > ema21 and close_p > open_p and low_p <= ema9 * 1.002:
                active_pos.append({'symbol': sym, 'side': 'BUY', 'entry': close_p, 'sl': close_p - sl_pts, 'stage': 0, 'qty': lot, 'is_opt': is_opt})
                symbol_traded[sym] = 1

    print(f"=== Date: {target_date} ===")
    print(f"Total Day PnL: Rs. {day_pnl:,.2f}")
    for item in ledger:
        print(f"  {item['symbol']:12}: PnL: Rs. {item['pnl']:+8.1f} | {item['reason']}")

test_single_day('2026-11-02')
print("-" * 50)
test_single_day('2026-11-04')
