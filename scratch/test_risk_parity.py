import pandas as pd
import numpy as np
import json
from test_scaled_performance import raw_candles

# Risk Parity Portfolio:
# Target Risk per trade ~ ₹2,000 - ₹2,500 across ALL instruments
# 1. CRUDEOIL: 1 lot (₹100/pt, SL 16 pts = ₹1,600 risk, TP2 42 pts = +₹4,200)
# 2. NATURALGAS: 1 lot (₹1,250/pt, SL 1.6 pts = ₹2,000 risk, TP2 4.0 pts = +₹5,000)
# 3. NATGASMINI: 4 lots (₹1,000/pt, SL 1.6 pts = ₹1,600 risk, TP2 4.0 pts = +₹4,000)
# 4. GOLDM: 3 lots (₹30/pt, SL 80 pts = ₹2,400 risk, TP2 200 pts = +₹6,000)
# 5. SILVERM: 4 lots (₹20/pt, SL 200 pts = ₹4,000 risk, TP2 450 pts = +₹9,000)
# 6. COPPER: If max_risk_cap = ₹2,000 (SL max 0.80 pts) OR let's check SL 0.8 pts with trailing

def test_risk_allocation(copper_weight=0.5, gold_lots=4, silver_lots=4, crude_lots=2, ng_lots=1, ngmini_lots=4):
    SPECS = {
        'CRUDEOIL': {
            'symbol': 'CRUDEOIL',
            'raw_sym': 'CRUDEOIL',
            'point_val': 100.0,
            'lots': crude_lots,
            'tick_size': 1.0,
            'min_sl': 14.0,
            'max_sl': 22.0,
            'min_tp': 28.0,
        },
        'NATURALGAS': {
            'symbol': 'NATURALGAS',
            'raw_sym': 'NATURALGAS',
            'point_val': 1250.0,
            'lots': ng_lots,
            'tick_size': 0.1,
            'min_sl': 1.4,
            'max_sl': 2.0,
            'min_tp': 2.6,
        },
        'GOLDM': {
            'symbol': 'GOLDM',
            'raw_sym': 'GOLD',
            'point_val': 10.0,
            'lots': gold_lots,
            'tick_size': 1.0,
            'min_sl': 75.0,
            'max_sl': 110.0,
            'min_tp': 140.0,
        },
        'SILVERM': {
            'symbol': 'SILVERM',
            'raw_sym': 'SILVER',
            'point_val': 5.0,
            'lots': silver_lots,
            'tick_size': 1.0,
            'min_sl': 180.0,
            'max_sl': 240.0,
            'min_tp': 300.0,
        },
        'NATGASMINI': {
            'symbol': 'NATGASMINI',
            'raw_sym': 'NATURALGAS',
            'point_val': 250.0,
            'lots': ngmini_lots,
            'tick_size': 0.1,
            'min_sl': 1.4,
            'max_sl': 2.2,
            'min_tp': 2.6,
        },
        'COPPER': {
            'symbol': 'COPPER',
            'raw_sym': 'COPPER',
            'point_val': 2500.0 * copper_weight,
            'lots': 1,
            'tick_size': 0.05,
            'min_sl': 1.2,
            'max_sl': 1.8,
            'min_tp': 2.2,
        }
    }

    all_trades = []
    
    for sym, spec in SPECS.items():
        if spec['lots'] <= 0 or spec['point_val'] <= 0:
            continue
        raw_sym = spec['raw_sym']
        candles = raw_candles.get(raw_sym, [])
        if len(candles) < 60:
            continue
            
        df = pd.DataFrame(candles)
        df['dt'] = pd.to_datetime(df['timestamp'], unit='ms') + pd.Timedelta(hours=5, minutes=30)
        df['date'] = df['dt'].dt.strftime('%Y-%m-%d')
        df['time'] = df['dt'].dt.strftime('%H:%M')
        
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        opens = df['open'].values
        volumes = df['volume'].values
        
        typ = (highs + lows + closes) / 3.0
        v = np.maximum(volumes, 1)
        cum_pv = np.cumsum(typ * v)
        cum_v = np.cumsum(v)
        vwap = cum_pv / cum_v
        
        std20 = pd.Series(typ).rolling(20, min_periods=5).std().fillna(1.0).values
        upper2 = vwap + 2.0 * std20
        lower2 = vwap - 2.0 * std20
        
        ema9 = pd.Series(closes).ewm(span=9, adjust=False).mean().values
        ema21 = pd.Series(closes).ewm(span=21, adjust=False).mean().values
        
        tr = np.maximum(highs - lows, np.maximum(abs(highs - np.roll(closes, 1)), abs(lows - np.roll(closes, 1))))
        tr[0] = highs[0] - lows[0]
        atr14 = pd.Series(tr).rolling(14, min_periods=5).mean().fillna(1.0).values
        
        hl2 = (highs + lows) / 2.0
        upper_band = hl2 + 2.0 * atr14
        lower_band = hl2 - 2.0 * atr14
        supertrend = np.full(len(df), 'BULL')
        for i in range(1, len(df)):
            if closes[i] > upper_band[i-1]:
                supertrend[i] = 'BULL'
            elif closes[i] < lower_band[i-1]:
                supertrend[i] = 'BEAR'
            else:
                supertrend[i] = supertrend[i-1]
                
        delta = pd.Series(closes).diff()
        gain = delta.clip(lower=0).rolling(9, min_periods=5).mean()
        loss = (-delta.clip(upper=0)).rolling(9, min_periods=5).mean()
        rs = gain / np.maximum(loss, 1e-8)
        rsi9 = (100 - (100 / (1 + rs))).fillna(50.0).values
        
        avg_vol = pd.Series(volumes).rolling(20, min_periods=5).mean().fillna(1.0).values
        rvol = np.maximum(volumes / np.maximum(avg_vol, 1.0), 0.1)
        
        body = abs(closes - opens)
        rng = np.maximum(highs - lows, 1e-8)
        body_ratio = body / rng
        roc3 = (closes - np.roll(closes, 3)) / np.maximum(atr14, 1e-8)
        roc3[:3] = 0.0
        ag_score = np.minimum(100.0, np.abs(roc3) * 35.0 + rvol * 25.0 + body_ratio * 30.0)
        
        upper_wick = (highs - np.maximum(opens, closes)) / rng
        lower_wick = (np.minimum(opens, closes) - lows) / rng
        
        active_pos = None
        last_exit_idx = -999
        
        for i in range(40, len(df)):
            c_time = df['time'].iloc[i]
            c_date = df['date'].iloc[i]
            h = int(c_time.split(':')[0])
            m = int(c_time.split(':')[1])
            mins = h * 60 + m
            is_session = (9 * 60 + 15) <= mins <= (23 * 60 + 20)
            
            if active_pos:
                closed = False
                exit_price = 0.0
                exit_reason = ""
                pos = active_pos
                
                if pos['action'] == 'BUY':
                    if lows[i] <= pos['sl_price']:
                        exit_price = pos['sl_price']
                        exit_reason = "TRAILED_SL_HIT" if pos['tp1_hit'] else "INITIAL_SL_HIT"
                        closed = True
                    elif highs[i] >= pos['tp2_price']:
                        exit_price = pos['tp2_price']
                        exit_reason = "TP2_RUNNER_TARGET_HIT"
                        closed = True
                    elif highs[i] >= pos['tp1_price'] and not pos['tp1_hit']:
                        pos['tp1_hit'] = True
                        pos['sl_price'] = pos['entry_price'] + spec['tick_size'] * 2
                else: # SELL
                    if highs[i] >= pos['sl_price']:
                        exit_price = pos['sl_price']
                        exit_reason = "TRAILED_SL_HIT" if pos['tp1_hit'] else "INITIAL_SL_HIT"
                        closed = True
                    elif lows[i] <= pos['tp2_price']:
                        exit_price = pos['tp2_price']
                        exit_reason = "TP2_RUNNER_TARGET_HIT"
                        closed = True
                    elif lows[i] <= pos['tp1_price'] and not pos['tp1_hit']:
                        pos['tp1_hit'] = True
                        pos['sl_price'] = pos['entry_price'] - spec['tick_size'] * 2
                        
                if not closed and mins >= (23 * 60 + 20):
                    exit_price = closes[i]
                    exit_reason = "AUTO_SQUARE_OFF_1120PM"
                    closed = True
                    
                if closed:
                    pts = (exit_price - pos['entry_price']) if pos['action'] == 'BUY' else (pos['entry_price'] - exit_price)
                    pnl = pts * spec['point_val'] * spec['lots']
                    all_trades.append({
                        'date': pos['entry_date'],
                        'symbol': sym,
                        'action': pos['action'],
                        'mode': pos['mode'],
                        'entry_time': pos['entry_time'],
                        'exit_time': c_time,
                        'entry_price': pos['entry_price'],
                        'exit_price': round(exit_price, 2),
                        'points': round(pts, 2),
                        'pnl': round(pnl, 2),
                        'reason': exit_reason
                    })
                    active_pos = None
                    last_exit_idx = i
                    
            if not active_pos and is_session and mins < (23 * 60 + 10) and (i - last_exit_idx >= 3):
                entry_price = closes[i]
                recent3_low = min(lows[i], lows[i-1], lows[i-2])
                recent3_high = max(highs[i], highs[i-1], highs[i-2])
                
                action = 'WAIT'
                mode = 'NONE'
                
                # Mode 1: AntiGravity Thrust
                is_bull_thrust = (
                    closes[i] > opens[i] and
                    closes[i] > highs[i-1] and
                    entry_price > vwap[i] and
                    ema9[i] >= ema21[i] and
                    supertrend[i] == 'BULL' and
                    body_ratio[i] >= 0.50 and
                    upper_wick[i] <= 0.25 and
                    rvol[i] >= 1.05 and
                    ag_score[i] >= 48.0 and
                    52 <= rsi9[i] <= 78
                )
                
                is_bear_thrust = (
                    closes[i] < opens[i] and
                    closes[i] < lows[i-1] and
                    entry_price < vwap[i] and
                    ema9[i] <= ema21[i] and
                    supertrend[i] == 'BEAR' and
                    body_ratio[i] >= 0.50 and
                    lower_wick[i] <= 0.25 and
                    rvol[i] >= 1.05 and
                    ag_score[i] >= 48.0 and
                    22 <= rsi9[i] <= 48
                )
                
                if is_bull_thrust:
                    action = 'BUY'
                    mode = 'ANTI_GRAVITY_THRUST'
                elif is_bear_thrust:
                    action = 'SELL'
                    mode = 'ANTI_GRAVITY_THRUST'
                    
                # Mode 2: VWAP + EMA9 Pullback Scalp
                if action == 'WAIT':
                    bull_pin = (closes[i] > opens[i] and upper_wick[i] <= 0.28 and 
                                (lower_wick[i] >= 0.32 or (closes[i-1] < opens[i-1] and closes[i] > (opens[i-1]+closes[i-1])/2)))
                    bear_pin = (closes[i] < opens[i] and lower_wick[i] <= 0.28 and 
                                (upper_wick[i] >= 0.32 or (closes[i-1] > opens[i-1] and closes[i] < (opens[i-1]+closes[i-1])/2)))
                    
                    touched_bull = (entry_price > vwap[i] and ema9[i] > ema21[i] and 
                                    recent3_low <= max(ema9[i], vwap[i]) * 1.002 and entry_price >= ema9[i])
                    touched_bear = (entry_price < vwap[i] and ema9[i] < ema21[i] and 
                                    recent3_high >= min(ema9[i], vwap[i]) * 0.998 and entry_price <= ema9[i])
                    
                    if touched_bull and bull_pin and (44 <= rsi9[i] <= 68) and rvol[i] >= 0.90 and ag_score[i] >= 45.0:
                        action = 'BUY'
                        mode = 'VWAP_EMA_PULLBACK_SCALP'
                    elif touched_bear and bear_pin and (32 <= rsi9[i] <= 56) and rvol[i] >= 0.90 and ag_score[i] >= 45.0:
                        action = 'SELL'
                        mode = 'VWAP_EMA_PULLBACK_SCALP'
                        
                # Mode 3: 2-Sigma Band Reversal
                if action == 'WAIT':
                    swept_lower = (recent3_low <= lower2[i] and closes[i] > opens[i] and 
                                   (lower_wick[i] >= 0.35 or body_ratio[i] >= 0.45) and rsi9[i] <= 36 and rsi9[i] > rsi9[i-1] and rvol[i] >= 1.0)
                    swept_upper = (recent3_high >= upper2[i] and closes[i] < opens[i] and 
                                   (upper_wick[i] >= 0.35 or body_ratio[i] >= 0.45) and rsi9[i] >= 64 and rsi9[i] < rsi9[i-1] and rvol[i] >= 1.0)
                    if swept_lower:
                        action = 'BUY'
                        mode = 'EXTREME_BAND_REVERSAL'
                    elif swept_upper:
                        action = 'SELL'
                        mode = 'EXTREME_BAND_REVERSAL'
                        
                if action != 'WAIT':
                    raw_sl = (entry_price - recent3_low + atr14[i] * 0.3) if action == 'BUY' else (recent3_high - entry_price + atr14[i] * 0.3)
                    clamped_sl = min(spec['max_sl'], max(spec['min_sl'], raw_sl))
                    sl_price = round(entry_price - clamped_sl if action == 'BUY' else entry_price + clamped_sl, 2)
                    
                    tp1_pts = max(spec['min_tp'], clamped_sl * 1.6)
                    tp2_pts = max(spec['min_tp'] * 1.6, clamped_sl * 2.6)
                    
                    tp1_price = round(entry_price + tp1_pts if action == 'BUY' else entry_price - tp1_pts, 2)
                    tp2_price = round(entry_price + tp2_pts if action == 'BUY' else entry_price - tp2_pts, 2)
                    
                    active_pos = {
                        'action': action,
                        'mode': mode,
                        'entry_date': c_date,
                        'entry_time': c_time,
                        'entry_price': entry_price,
                        'sl_price': sl_price,
                        'tp1_price': tp1_price,
                        'tp2_price': tp2_price,
                        'tp1_hit': False
                    }
                    
    return pd.DataFrame(all_trades)

# Test 1: Copper weight 0.0 (No copper)
df_no_copper = test_risk_allocation(copper_weight=0.0, gold_lots=4, silver_lots=4, crude_lots=2, ng_lots=1, ngmini_lots=4)
print("\n" + "="*85)
print("TEST: RISK-SCALED COMMODITY BASKET (GOLDM 4, SILVERM 4, CRUDE 2, NG 1, NGMINI 4)")
print("="*85)
for d, sub in df_no_copper.groupby('date'):
    wins = sub[sub['pnl'] > 0]
    losses = sub[sub['pnl'] < 0]
    gp = wins['pnl'].sum()
    gl = losses['pnl'].sum()
    net = sub['pnl'].sum()
    wr = len(wins) / len(sub) * 100 if len(sub) else 0
    print(f"{d:<12} | Trades: {len(sub):<3} | Wins: {len(wins):<2} | Losses: {len(losses):<2} | WinRate: {wr:>5.1f}% | Gross Win: +₹{gp:>10,.2f} | Gross Loss: ₹{gl:>10,.2f} | Net P&L: ₹{net:>+11,.2f}")

tot = df_no_copper['pnl'].sum()
days = df_no_copper['date'].nunique()
wins = df_no_copper[df_no_copper['pnl'] > 0]
print("="*85)
print(f"TOTAL REAL PROFIT (4 DAYS): ₹{tot:+,.2f}")
print(f"AVERAGE PROFIT PER DAY:     ₹{tot/days:+,.2f} / day")
print(f"OVERALL WIN RATE:           {len(wins)/len(df_no_copper)*100:.1f}%")
print(f"TOTAL TRADES:               {len(df_no_copper)} ({len(df_no_copper)/days:.1f}/day)")
print("="*85)
