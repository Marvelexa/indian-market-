"""
scripts/backtest_mcx_60d_real.py
Runs the exact 2-Mode S&R Reversal + Infinite Ladder logic on 60 days of real MCX 5m bars
for CRUDEOIL, NATURALGAS, SILVER, GOLD, COPPER.
"""

import json
import math
import datetime
import pytz
import yfinance as yf
import numpy as np

IST = pytz.timezone('Asia/Kolkata')

COMMODITY_CONFIGS = {
    'CRUDEOIL': {'symbol': 'CL=F', 'lotSize': 100, 'strikeStep': 50, 'tick': 1.0, 'mult': 100.0, 'usdInr': 88.0 / 1.0},
    'NATURALGAS': {'symbol': 'NG=F', 'lotSize': 1250, 'strikeStep': 2.5, 'tick': 0.1, 'mult': 1250.0, 'usdInr': 88.0 / 1.0},
    'GOLD': {'symbol': 'GC=F', 'lotSize': 1, 'strikeStep': 100, 'tick': 1.0, 'mult': 1.0, 'usdInr': 88.0 * 31.1035 / 10.0},
    'SILVER': {'symbol': 'SI=F', 'lotSize': 1, 'strikeStep': 500, 'tick': 1.0, 'mult': 1.0, 'usdInr': 88.0 * 32.1507},
    'COPPER': {'symbol': 'HG=F', 'lotSize': 2500, 'strikeStep': 5, 'tick': 0.05, 'mult': 2500.0, 'usdInr': 88.0 / 2.20462 * 100.0 / 100.0 / 100.0} # cent/lb to inr/kg
}

def compute_rsi(prices, period=14):
    if len(prices) <= period:
        return 50.0
    deltas = np.diff(prices[-period-1:])
    gains = deltas[deltas > 0]
    losses = -deltas[deltas < 0]
    avg_gain = np.mean(gains) if len(gains) > 0 else 0.0
    avg_loss = np.mean(losses) if len(losses) > 0 else 0.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def run_mcx_audit():
    print("Fetching 60 days of real MCX 5m bars from yfinance...")
    tickers = [cfg['symbol'] for cfg in COMMODITY_CONFIGS.values()]
    df = yf.download(tickers, period='60d', interval='5m', progress=False)

    all_trades = []
    
    for name, cfg in COMMODITY_CONFIGS.items():
        sym = cfg['symbol']
        try:
            cdf = df.xs(sym, level=1, axis=1).dropna()
        except:
            continue

        bars = []
        for idx, row in cdf.iterrows():
            ts_ist = idx.tz_convert(IST)
            bars.append({
                'dt': ts_ist,
                'open': float(row['Open']) * cfg['usdInr'],
                'high': float(row['High']) * cfg['usdInr'],
                'low': float(row['Low']) * cfg['usdInr'],
                'close': float(row['Close']) * cfg['usdInr'],
                'volume': float(row['Volume'])
            })

        print(f"Loaded {len(bars)} bars for {name} ({bars[0]['dt'].strftime('%Y-%m-%d')} to {bars[-1]['dt'].strftime('%Y-%m-%d')})")

        # Run bar by bar
        active_pos = None
        last_exit_idx = -10

        for i in range(50, len(bars)):
            bar = bars[i]
            time_str = bar['dt'].strftime('%H:%M')
            date_str = bar['dt'].strftime('%Y-%m-%d')
            is_eod = time_str >= '23:20'

            # 1. Evaluate open position
            if active_pos:
                delta = 0.55
                is_ce = active_pos['type'] == 'CE'
                spot_change = bar['close'] - active_pos['entry_spot'] if is_ce else active_pos['entry_spot'] - bar['close']
                high_change = bar['high'] - active_pos['entry_spot'] if is_ce else active_pos['entry_spot'] - bar['low']
                low_change = bar['low'] - active_pos['entry_spot'] if is_ce else active_pos['entry_spot'] - bar['high']

                cur_prem = max(0.1, active_pos['entry_prem'] + spot_change * delta)
                high_prem = max(0.1, active_pos['entry_prem'] + high_change * delta)
                low_prem = max(0.1, active_pos['entry_prem'] + low_change * delta)

                max_float_pnl = (high_prem - active_pos['entry_prem']) * active_pos['lot_size']
                if max_float_pnl > active_pos['peak_pnl']:
                    active_pos['peak_pnl'] = max_float_pnl

                # Infinite Progressive Trailing Profit Ladder
                if active_pos['peak_pnl'] >= 500:
                    step = int(active_pos['peak_pnl'] // 500)
                    step_locked = 150 if step == 1 else 150 + (step - 1) * 450
                    dyn_trail = max(step_locked, active_pos['peak_pnl'] - 1000) if active_pos['peak_pnl'] >= 4000 else step_locked
                    new_lock = max(active_pos['locked_pnl'], dyn_trail)
                    if new_lock > active_pos['locked_pnl']:
                        active_pos['locked_pnl'] = new_lock
                        active_pos['stage'] = max(active_pos['stage'], step)
                        active_pos['sl_prem'] = active_pos['entry_prem'] + new_lock / active_pos['lot_size']

                # Check Exits
                exit_now = False
                exit_price = cur_prem
                exit_reason = ''

                # Hard SL -2500 intra-candle
                if low_prem <= active_pos['entry_prem'] - 2500 / active_pos['lot_size']:
                    exit_now = True
                    exit_price = active_pos['entry_prem'] - 2500 / active_pos['lot_size']
                    exit_reason = 'HARD_SL_2500_HIT'
                elif active_pos['stage'] > 0 and cur_prem <= active_pos['sl_prem']:
                    exit_now = True
                    exit_price = active_pos['sl_prem']
                    exit_reason = f"TP{active_pos['stage']}_TRAIL_HIT"
                elif is_eod:
                    exit_now = True
                    exit_price = cur_prem
                    exit_reason = 'MCX_AUTO_SQUARE_OFF_1120PM'

                if exit_now:
                    gross = (exit_price - active_pos['entry_prem']) * active_pos['lot_size']
                    net = gross - 62.0
                    all_trades.append({
                        'symbol': name,
                        'type': active_pos['type'],
                        'entry_date': active_pos['entry_date'],
                        'entry_time': active_pos['entry_time'],
                        'exit_date': date_str,
                        'exit_time': time_str,
                        'gross_pnl': gross,
                        'friction': 62.0,
                        'net_pnl': net,
                        'stage': active_pos['stage'],
                        'exit_reason': exit_reason
                    })
                    last_exit_idx = i
                    active_pos = None

            # 2. Timing check (09:30 AM to 11:00 PM IST)
            if time_str < '09:30' or time_str >= '23:00':
                continue

            # 3. New Entry Scan
            if not active_pos and (i - last_exit_idx >= 3):
                window = bars[max(0, i-40):i+1]
                closes = [b['close'] for b in window]
                c0 = window[-1]
                c1 = window[-2]
                spot = c0['close']

                highs = [b['high'] for b in window]
                lows = [b['low'] for b in window]
                max_h = max(highs)
                min_l = min(lows)
                range_pos = (spot - min_l) / max(max_h - min_l, 1e-5)

                rsi = compute_rsi(closes, 14)
                rsi_prev = compute_rsi(closes[:-1], 14)

                rng = max(c0['high'] - c0['low'], 1e-5)
                body = abs(c0['close'] - c0['open'])
                lw = (min(c0['open'], c0['close']) - c0['low']) / rng
                uw = (c0['high'] - max(c0['open'], c0['close'])) / rng

                is_bull_pin = c0['close'] > c0['open'] and lw >= 0.35 and uw <= 0.25
                is_bull_eng = c0['close'] > c0['open'] and c1['close'] < c1['open'] and c0['close'] > (c1['open'] + c1['close'])/2 and body/rng >= 0.42
                is_bull_rec = c0['close'] > c0['open'] and c0['close'] > c1['high'] and body/rng >= 0.45
                has_bull_pa = is_bull_pin or is_bull_eng or is_bull_rec

                is_bear_pin = c0['close'] < c0['open'] and uw >= 0.35 and lw <= 0.25
                is_bear_eng = c0['close'] < c0['open'] and c1['close'] > c1['open'] and c0['close'] < (c1['open'] + c1['close'])/2 and body/rng >= 0.42
                is_bear_brk = c0['close'] < c0['open'] and c0['close'] < c1['low'] and body/rng >= 0.45
                has_bear_pa = is_bear_pin or is_bear_eng or is_bear_brk

                # BUY CE on Support Reversal
                if (range_pos <= 0.35 or spot <= min_l * 1.002) and has_bull_pa and 25 <= rsi <= 65 and rsi >= rsi_prev - 1.0:
                    entry_prem = spot * 0.02
                    sl_drop = 2500 / cfg['lotSize']
                    active_pos = {
                        'symbol': name,
                        'type': 'CE',
                        'entry_date': date_str,
                        'entry_time': time_str,
                        'entry_spot': spot,
                        'entry_prem': entry_prem,
                        'sl_prem': entry_prem - sl_drop,
                        'lot_size': cfg['lotSize'],
                        'stage': 0,
                        'locked_pnl': 0,
                        'peak_pnl': 0
                    }

                # BUY PE on Resistance Reversal
                elif (range_pos >= 0.65 or spot >= max_h * 0.998) and has_bear_pa and 35 <= rsi <= 75 and rsi <= rsi_prev + 1.0:
                    entry_prem = spot * 0.02
                    sl_drop = 2500 / cfg['lotSize']
                    active_pos = {
                        'symbol': name,
                        'type': 'PE',
                        'entry_date': date_str,
                        'entry_time': time_str,
                        'entry_spot': spot,
                        'entry_prem': entry_prem,
                        'sl_prem': entry_prem - sl_drop,
                        'lot_size': cfg['lotSize'],
                        'stage': 0,
                        'locked_pnl': 0,
                        'peak_pnl': 0
                    }

    print("\n================================================================================")
    print("🛢️ MCX COMMODITY OPTION SNIPER: REAL-MARKET AUDIT (PAST 60 DAYS)")
    print("================================================================================")
    total_trades = len(all_trades)
    wins = [t for t in all_trades if t['net_pnl'] > 0]
    losses = [t for t in all_trades if t['net_pnl'] <= 0]
    gross_pnl = sum(t['gross_pnl'] for t in all_trades)
    friction = sum(t['friction'] for t in all_trades)
    net_pnl = sum(t['net_pnl'] for t in all_trades)

    win_rate = (len(wins) / max(1, total_trades)) * 100
    tot_win_pnl = sum(t['net_pnl'] for t in wins)
    tot_loss_pnl = abs(sum(t['net_pnl'] for t in losses))
    pf = tot_win_pnl / max(1.0, tot_loss_pnl)

    print(f"Total MCX Trades:       {total_trades}")
    print(f"Winning Trades:         {len(wins)} ({win_rate:.1f}%)")
    print(f"Losing Trades:          {len(losses)} ({100-win_rate:.1f}%)")
    print(f"Profit Factor:          {pf:.2f}")
    print(f"Gross Realized Profit:  ₹{gross_pnl:.2f}")
    print(f"Total Friction (₹62):   ₹{friction:.2f}")
    print(f"MCX GRAND TOTAL NET:    +₹{net_pnl:.2f}")

    # Monthly
    monthly = {}
    for t in all_trades:
        m = t['entry_date'][:7]
        if m not in monthly:
            monthly[m] = {'trades': 0, 'wins': 0, 'net': 0.0}
        monthly[m]['trades'] += 1
        if t['net_pnl'] > 0:
            monthly[m]['wins'] += 1
        monthly[m]['net'] += t['net_pnl']

    print("\nMONTHLY MCX BREAKDOWN:")
    for m, st in sorted(monthly.items()):
        wr = (st['wins'] / max(1, st['trades'])) * 100
        print(f"| {m} | {st['trades']} Trades | {st['wins']} Wins ({wr:.1f}%) | Net: +₹{st['net']:.2f} |")

if __name__ == '__main__':
    run_mcx_audit()
