import urllib.request
import json
import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np

ist = ZoneInfo('Asia/Kolkata')

# Fetch 15-minute CL=F data from Yahoo Finance API for the last 60 days
url_15m = 'https://query1.finance.yahoo.com/v8/finance/chart/CL=F?interval=15m&range=60d'
req = urllib.request.Request(url_15m, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req)
data_15m = json.loads(resp.read().decode())['chart']['result'][0]

ts_15 = data_15m['timestamp']
q_15 = data_15m['indicators']['quote'][0]

usd_inr = 88.0
bars = []
for i in range(len(ts_15)):
    t = ts_15[i]
    o = q_15['open'][i]
    h = q_15['high'][i]
    l = q_15['low'][i]
    c = q_15['close'][i]
    v = q_15['volume'][i]
    if o is None or c is None: continue
    dt = datetime.datetime.fromtimestamp(t, ist)
    bars.append({
        "timestamp": t,
        "date": dt.strftime("%Y-%m-%d"),
        "time": dt.strftime("%H:%M:%S"),
        "weekday": dt.strftime("%A"),
        "open": round(o * usd_inr, 1),
        "high": round(h * usd_inr, 1),
        "low": round(l * usd_inr, 1),
        "close": round(c * usd_inr, 1),
        "volume": v or 1
    })

df = pd.DataFrame(bars)
df = df[df['date'] <= '2026-11-13'].copy()
dates = sorted(df['date'].unique())

LOT_SIZE = 100
DELTA = 0.60
ROUND_TRIP_COST = 100.0

def test_crude_peak(min_trend_pts=6.0, target_tp6=3500.0, eia_shield=True):
    daily_ledger = []
    total_pnl = 0.0
    total_trades = 0
    total_wins = 0
    total_losses = 0

    for d in dates:
        d_bars = df[df['date'] == d].copy().reset_index(drop=True)
        # 17:15 to 23:15
        ev_bars = d_bars[(d_bars['time'] >= '17:15:00') & (d_bars['time'] <= '23:15:00')].reset_index(drop=True)
        if len(ev_bars) < 8: continue

        day_pnl = 0.0
        day_trades = 0
        day_wins = 0
        day_losses = 0
        circuit_breaker_hit = False

        active_pos = None

        for idx in range(len(ev_bars)):
            c_bar = ev_bars.iloc[idx]
            close_p = c_bar['close']
            open_p = c_bar['open']
            high_p = c_bar['high']
            low_p = c_bar['low']
            bar_time = c_bar['time']
            weekday = c_bar['weekday']

            prior = d_bars[d_bars['timestamp'] <= c_bar['timestamp']]
            closes = prior['close'].tolist()

            k9 = 2.0 / 10
            k21 = 2.0 / 22
            e9 = closes[0]
            e21 = closes[0]
            for cl in closes:
                e9 = cl * k9 + e9 * (1 - k9)
                e21 = cl * k21 + e21 * (1 - k21)

            pv = sum(((b['high'] + b['low'] + b['close']) / 3.0) * b['volume'] for _, b in prior.iterrows())
            vol_sum = prior['volume'].sum()
            vwap = pv / vol_sum if vol_sum > 0 else close_p

            # 1. Manage Active Position (WORST-CASE INTRA-BAR: ADVERSE FIRST)
            if active_pos:
                is_buy = active_pos['side'] == 'BUY'
                entry_p = active_pos['entry_price']

                worst_p = low_p if is_buy else high_p
                adverse_pts = (entry_p - worst_p) if is_buy else (worst_p - entry_p)
                adverse_loss = adverse_pts * DELTA * LOT_SIZE

                exit_reason = None
                exit_pnl = 0.0

                if active_pos['stage'] == 0:
                    if adverse_loss >= 1500.0:
                        exit_reason = "MAX_LOSS_CAP_HIT"
                        exit_pnl = -1500.0 - ROUND_TRIP_COST
                    elif adverse_loss >= 500.0 and ((is_buy and close_p < vwap) or (not is_buy and close_p > vwap)):
                        exit_reason = "SMART_SL_EXIT"
                        exit_pnl = -550.0 - ROUND_TRIP_COST
                else:
                    cur_trail_loss = (entry_p + active_pos['lock_pts'] - worst_p) if is_buy else (worst_p - (entry_p - active_pos['lock_pts']))
                    if cur_trail_loss > 0:
                        exit_reason = f"TP_{active_pos['stage']}_LOCK_EXIT"
                        exit_pnl = (active_pos['lock_pts'] * DELTA * LOT_SIZE) - ROUND_TRIP_COST

                if not exit_reason:
                    best_p = high_p if is_buy else low_p
                    pt_gain = (best_p - entry_p) if is_buy else (entry_p - best_p)
                    peak_rupee = max(active_pos['peak_rupee'], pt_gain * DELTA * LOT_SIZE)
                    active_pos['peak_rupee'] = peak_rupee

                    # 6-Stage Ladder
                    if active_pos['stage'] == 0 and peak_rupee >= 500.0:
                        active_pos['stage'] = 1
                        active_pos['lock_pts'] = 300.0 / (DELTA * LOT_SIZE)
                    if active_pos['stage'] <= 1 and peak_rupee >= 1000.0:
                        active_pos['stage'] = 2
                        active_pos['lock_pts'] = 700.0 / (DELTA * LOT_SIZE)
                    if active_pos['stage'] <= 2 and peak_rupee >= 1500.0:
                        active_pos['stage'] = 3
                        active_pos['lock_pts'] = 1150.0 / (DELTA * LOT_SIZE)
                    if active_pos['stage'] <= 3 and peak_rupee >= 2000.0:
                        active_pos['stage'] = 4
                        active_pos['lock_pts'] = 1600.0 / (DELTA * LOT_SIZE)
                    if active_pos['stage'] <= 4 and peak_rupee >= 2500.0:
                        active_pos['stage'] = 5
                        active_pos['lock_pts'] = 2100.0 / (DELTA * LOT_SIZE)

                    if peak_rupee >= target_tp6:
                        exit_reason = "TP_TARGET_EXIT"
                        exit_pnl = target_tp6 - ROUND_TRIP_COST

                if not exit_reason and idx == len(ev_bars) - 1:
                    exit_reason = "EOD_SQUAREOFF"
                    diff = (close_p - entry_p) if is_buy else (entry_p - close_p)
                    exit_pnl = (diff * DELTA * LOT_SIZE) - ROUND_TRIP_COST

                if exit_reason:
                    day_pnl += exit_pnl
                    day_trades += 1
                    if exit_pnl > 0: day_wins += 1
                    else: day_losses += 1
                    active_pos = None

                    if day_pnl <= -2500.0:
                        circuit_breaker_hit = True

            # 2. Evaluate New Entry (Clean Trend Confirmation)
            if not active_pos and not circuit_breaker_hit and day_trades < 2 and idx < len(ev_bars) - 3:
                # Wednesday EIA shield
                if eia_shield and weekday == "Wednesday" and "19:45:00" <= bar_time <= "20:30:00":
                    continue

                # EMA separation
                if abs(e9 - e21) < min_trend_pts:
                    continue

                if close_p > vwap and e9 > e21 and close_p > open_p and low_p <= e9 * 1.002:
                    active_pos = {
                        "side": "BUY",
                        "entry_price": close_p,
                        "peak_rupee": 0.0,
                        "stage": 0,
                        "lock_pts": 0.0
                    }
                elif close_p < vwap and e9 < e21 and close_p < open_p and high_p >= e9 * 0.998:
                    active_pos = {
                        "side": "SELL",
                        "entry_price": close_p,
                        "peak_rupee": 0.0,
                        "stage": 0,
                        "lock_pts": 0.0
                    }

        total_pnl += day_pnl
        total_trades += day_trades
        total_wins += day_wins
        total_losses += day_losses

        daily_ledger.append({
            "date": d,
            "month": d[:7],
            "trades": day_trades,
            "wins": day_wins,
            "losses": day_losses,
            "pnl": round(day_pnl, 2),
            "is_green": day_pnl > 0
        })

    df_d = pd.DataFrame(daily_ledger)
    m_grp = df_d.groupby('month').agg(
        days=('date', 'count'),
        trades=('trades', 'sum'),
        wins=('wins', 'sum'),
        losses=('losses', 'sum'),
        net_pnl=('pnl', 'sum'),
        green=('is_green', lambda x: x.sum())
    )
    m_grp['wr'] = (m_grp['wins'] / m_grp['trades'] * 100).round(1)
    m_grp['roe'] = (m_grp['net_pnl'] / 20000.0 * 100).round(1)
    return total_pnl, total_trades, total_wins, total_losses, m_grp

for sep in [4.0, 6.0, 8.0]:
    for tp_target in [3000.0, 3500.0]:
        pnl, trades, wins, losses, m_grp = test_crude_peak(min_trend_pts=sep, target_tp6=tp_target)
        wr = (wins / trades * 100) if trades > 0 else 0
        print(f"EMA Sep: {sep} | Target: {tp_target} -> Total: INR {pnl:,.2f} | Trades: {trades} | WR: {wr:.1f}%")
        for m, r in m_grp.iterrows():
            print(f"   {m}: {r['trades']}T ({r['wr']}%) -> INR {r['net_pnl']:,.2f}")
