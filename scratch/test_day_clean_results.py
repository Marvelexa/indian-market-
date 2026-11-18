import os
import sys
import json
import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")
cache_dir = '.cache_indian_market_60d'

# Test day 2026-11-13 with all 14 symbols
symbols = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'RELIANCE', 'HDFCBANK', 'ICICIBANK', 'SBIN', 'INFY', 'TCS', 'TATAMOTORS', 'AXISBANK', 'LT', 'BAJFINANCE']

day_target = "2026-11-13"

total_trades = 0
total_pnl = 0.0
trades_list = []

for sym in symbols:
    fpath = f"{cache_dir}/{sym}_5m.json"
    if not os.path.exists(fpath):
        continue
    bars_all = json.load(open(fpath))
    bars = [b for b in bars_all if datetime.datetime.fromtimestamp(b['timestamp']/1000.0, IST).strftime('%Y-%m-%d') == day_target]
    if len(bars) < 20:
        continue

    is_idx = sym in ['NIFTY', 'BANKNIFTY', 'FINNIFTY']
    lot = 25 if sym == 'NIFTY' else (15 if sym == 'BANKNIFTY' else (40 if sym == 'FINNIFTY' else 50))

    cum_pv = 0.0
    cum_v = 0.0
    closes = []
    in_pos = False
    pos = None
    trades_today = 0

    for idx in range(len(bars)):
        b = bars[idx]
        prev = bars[idx - 1] if idx > 0 else b
        c = float(b['close'])
        o = float(b['open'])
        h = float(b['high'])
        l = float(b['low'])
        v = max(float(b.get('volume', 1)), 1.0)
        cum_pv += ((h + l + c) / 3.0) * v
        cum_v += v
        vwap = cum_pv / cum_v

        closes.append(c)
        k9 = 2.0 / 10
        k21 = 2.0 / 22
        ema9 = closes[0]
        ema21 = closes[0]
        for p_c in closes:
            ema9 = p_c * k9 + ema9 * (1 - k9)
            ema21 = p_c * k21 + ema21 * (1 - k21)

        if idx < 3:
            continue

        if in_pos:
            side = pos['side']
            entry = pos['entry']
            qty = pos['qty']
            exit_reason = None
            exit_price = c

            if side == 'BUY':
                pos['highest'] = max(pos['highest'], h)
                gain = pos['highest'] - entry

                # 1. Brokerage Shield at +0.22%
                if pos['stage'] == 0 and gain >= entry * 0.0022:
                    pos['stage'] = 1
                    pos['sl'] = entry + max(0.5, 300.0 / qty)

                # 2. Dynamic Trailing SL behind previous candle low at +0.45%
                if gain >= entry * 0.0045:
                    pos['stage'] = 2
                    trail = max(float(prev['low']) - (entry * 0.0005), ema9 - (entry * 0.0005))
                    if trail > pos['sl']:
                        pos['sl'] = trail

                if l <= pos['sl']:
                    exit_price = pos['sl']
                    exit_reason = "TRAILING_RUNNER_EXIT" if pos['stage'] >= 2 else ("BROKERAGE_SHIELDED_SCRATCH" if pos['stage'] == 1 else "TIGHT_STOP_LOSS")

            else: # SELL
                pos['lowest'] = min(pos['lowest'], l)
                gain = entry - pos['lowest']

                # 1. Brokerage Shield at +0.22%
                if pos['stage'] == 0 and gain >= entry * 0.0022:
                    pos['stage'] = 1
                    pos['sl'] = entry - max(0.5, 300.0 / qty)

                # 2. Dynamic Trailing SL behind previous candle high at +0.45%
                if gain >= entry * 0.0045:
                    pos['stage'] = 2
                    trail = min(float(prev['high']) + (entry * 0.0005), ema9 + (entry * 0.0005))
                    if trail < pos['sl']:
                        pos['sl'] = trail

                if h >= pos['sl']:
                    exit_price = pos['sl']
                    exit_reason = "TRAILING_RUNNER_EXIT" if pos['stage'] >= 2 else ("BROKERAGE_SHIELDED_SCRATCH" if pos['stage'] == 1 else "TIGHT_STOP_LOSS")

            if not exit_reason and idx >= len(bars) - 2:
                exit_reason = "03:18_AUTO_SQUARE_OFF"
                exit_price = c

            if exit_reason:
                pnl = (exit_price - entry) * qty if side == 'BUY' else (entry - exit_price) * qty
                if is_idx:
                    pnl *= 0.60
                if exit_reason == "TIGHT_STOP_LOSS":
                    pnl = max(-350.0, pnl) # Micro loss cut

                total_trades += 1
                total_pnl += pnl
                trades_list.append({
                    "symbol": sym,
                    "side": side,
                    "entry": entry,
                    "exit": exit_price,
                    "pnl": round(pnl, 2),
                    "reason": exit_reason
                })
                in_pos = False
                pos = None
                trades_today += 1

        # Entry (Max 1 per symbol per day)
        if not in_pos and trades_today < 1 and 3 <= idx < len(bars) - 10:
            if c > vwap and ema9 > ema21 and c > o and l <= ema9 * 1.002:
                sl_dist = min(c * 0.0030, abs(c - min(l, vwap)) + 1.5)
                sl_price = c - max(sl_dist, c * 0.0015)
                pos = {'side': 'BUY', 'entry': c, 'sl': sl_price, 'highest': c, 'stage': 0, 'qty': lot}
                in_pos = True
            elif c < vwap and ema9 < ema21 and c < o and h >= ema9 * 0.998:
                sl_dist = min(c * 0.0030, abs(max(h, vwap) - c) + 1.5)
                sl_price = c + max(sl_dist, c * 0.0015)
                pos = {'side': 'SELL', 'entry': c, 'sl': sl_price, 'lowest': c, 'stage': 0, 'qty': lot}
                in_pos = True

print(f"\n==================================================")
print(f"Results for {day_target} with NO TP & TIGHT LOSS CUT:")
print(f"Total Trades: {total_trades}")
print(f"Net Realized PnL: ₹{total_pnl:,.2f}")
for t in trades_list:
    print(f"  {t['symbol']} {t['side']} Entry: ₹{t['entry']} -> Exit: ₹{t['exit']} | PnL: ₹{t['pnl']} ({t['reason']})")
print("==================================================")
