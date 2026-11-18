import sys
sys.path.insert(0, '.')
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

def test_day(date_str, be_trigger, tp1, tp2, tp3):
    d_data = by_day_data.get(date_str, {})
    nifty_bars = d_data.get('NIFTY', [])
    active_pos = []
    symbol_traded = {}
    trades_log = []

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

            pt_gain = (h - entry) if is_buy else (entry - l)
            rupee_gain = pt_gain * qty * (0.60 if is_opt else 1.0)

            # Milestones
            if pos['stage'] == 0 and rupee_gain >= be_trigger:
                pos['stage'] = 1
                pos['sl'] = entry

            if pos['stage'] <= 1 and rupee_gain >= tp1:
                pos['stage'] = 2
                locked_pts = (be_trigger / (qty * 0.60 if is_opt else qty))
                pos['sl'] = entry + locked_pts if is_buy else entry - locked_pts

            if pos['stage'] <= 2 and rupee_gain >= tp2:
                pos['stage'] = 3
                locked_pts = (tp1 / (qty * 0.60 if is_opt else qty))
                pos['sl'] = entry + locked_pts if is_buy else entry - locked_pts

            if pos['stage'] >= 3:
                prev_b = bars[idx - 1]
                trail = float(prev_b['low']) if is_buy else float(prev_b['high'])
                if is_buy and trail > pos['sl']: pos['sl'] = trail
                elif not is_buy and trail < pos['sl']: pos['sl'] = trail

            exit_r = None
            exit_p = c
            if is_buy and l <= pos['sl']:
                exit_p = pos['sl']
                stage_val = pos['stage']
                exit_r = 'SL_EXIT' if stage_val == 0 else f'TP_{stage_val}_EXIT'
            elif not is_buy and h >= pos['sl']:
                exit_p = pos['sl']
                stage_val = pos['stage']
                exit_r = 'SL_EXIT' if stage_val == 0 else f'TP_{stage_val}_EXIT'
            elif idx >= min(72, len(bars) - 2):
                exit_r = '03:18_EOD'

            if exit_r:
                pt_move = (exit_p - entry) if is_buy else (entry - exit_p)
                pnl = pt_move * qty * (0.60 if is_opt else 1.0)
                if pnl < -1500.0: pnl = -1500.0
                trades_log.append({
                    'symbol': sym,
                    'side': pos['side'],
                    'entry': entry,
                    'exit': exit_p,
                    'pnl': round(pnl, 2),
                    'stage': pos['stage'],
                    'reason': exit_r
                })
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

    return trades_log

print("=== COMPARISON ON 2026-11-04 ===")
tight_trades = test_day('2026-11-04', 300, 750, 1500, 3000)
print(f"[TIGHT MODEL (BE at 300)]: Total PnL = ₹{sum(t['pnl'] for t in tight_trades):,.2f}")
for t in tight_trades:
    print(f"  {t['symbol']:12} {t['side']} | PnL: ₹{t['pnl']:>8} | Reason: {t['reason']}")

room_trades = test_day('2026-11-04', 1500, 3000, 6000, 12000)
print(f"\n[INSTITUTIONAL MODEL (BE at 1500 / 3000 / 6000)]: Total PnL = ₹{sum(t['pnl'] for t in room_trades):,.2f}")
for t in room_trades:
    print(f"  {t['symbol']:12} {t['side']} | PnL: ₹{t['pnl']:>8} | Reason: {t['reason']}")
