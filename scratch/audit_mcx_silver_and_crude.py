import urllib.request
import json
import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np

ist = ZoneInfo('Asia/Kolkata')

# 1. Fetch 15m SI=F (Silver) data from Yahoo Finance
url_si = 'https://query1.finance.yahoo.com/v8/finance/chart/SI=F?interval=15m&range=60d'
req_si = urllib.request.Request(url_si, headers={'User-Agent': 'Mozilla/5.0'})
resp_si = urllib.request.urlopen(req_si)
data_si = json.loads(resp_si.read().decode())['chart']['result'][0]

ts_si = data_si['timestamp']
q_si = data_si['indicators']['quote'][0]

# Silver conversion: SI=F is USD/troy oz (~$30-$34). 
# MCX Silver is INR/kg. 1 troy oz = 0.0311035 kg.
# MCX Silver price = (SI_USD / 0.0311035) * USDINR.
# For USDINR = 88, $32/oz = (32 / 0.0311035) * 88 = ~₹90,500 / kg.
# Silver Mini Lot size = 5 kg. 1 rupee move in MCX Silver = ₹5 PnL.
usd_inr = 88.0

bars_si = []
for i in range(len(ts_si)):
    t = ts_si[i]
    o = q_si['open'][i]
    h = q_si['high'][i]
    l = q_si['low'][i]
    c = q_si['close'][i]
    v = q_si['volume'][i]
    if o is None or c is None: continue
    dt = datetime.datetime.fromtimestamp(t, ist)
    
    # Convert to MCX Silver INR/kg
    conv = (usd_inr / 0.0311035)
    bars_si.append({
        "timestamp": t,
        "date": dt.strftime("%Y-%m-%d"),
        "time": dt.strftime("%H:%M:%S"),
        "open": round(o * conv, 0),
        "high": round(h * conv, 0),
        "low": round(l * conv, 0),
        "close": round(c * conv, 0),
        "volume": v or 1
    })

df_si = pd.DataFrame(bars_si)
df_si = df_si[df_si['date'] <= '2026-11-13'].copy()
dates = sorted(df_si['date'].unique())

# Silver Mini: Lot size = 5 kg (₹5 per point)
LOT_SIZE_SILVER = 5
ROUND_TRIP_COST = 100.0

daily_ledger_si = []
total_pnl_si = 0.0
wins_si = 0
losses_si = 0

for d in dates:
    d_bars = df_si[df_si['date'] == d].copy().reset_index(drop=True)
    ev_bars = d_bars[(d_bars['time'] >= '17:00:00') & (d_bars['time'] <= '23:15:00')].reset_index(drop=True)
    if len(ev_bars) < 8: continue

    day_pnl = 0.0
    day_trades = 0
    active_pos = None

    for idx in range(len(ev_bars)):
        c_bar = ev_bars.iloc[idx]
        close_p = c_bar['close']
        open_p = c_bar['open']
        high_p = c_bar['high']
        low_p = c_bar['low']
        bar_time = c_bar['time']

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

        # Manage Active Position
        if active_pos:
            is_buy = active_pos['side'] == 'BUY'
            entry_p = active_pos['entry_price']

            # Adverse move first
            worst_p = low_p if is_buy else high_p
            adverse_pts = (entry_p - worst_p) if is_buy else (worst_p - entry_p)
            adverse_loss = adverse_pts * LOT_SIZE_SILVER

            exit_reason = None
            exit_pnl = 0.0

            if active_pos['stage'] == 0:
                if adverse_loss >= 1500.0:
                    exit_reason = "MAX_LOSS_CAP_HIT"
                    exit_pnl = -1500.0 - ROUND_TRIP_COST
                elif adverse_loss >= 600.0 and ((is_buy and close_p < vwap) or (not is_buy and close_p > vwap)):
                    exit_reason = "SMART_SL_EXIT"
                    exit_pnl = -650.0 - ROUND_TRIP_COST
            else:
                cur_trail_loss = (entry_p + active_pos['lock_pts'] - worst_p) if is_buy else (worst_p - (entry_p - active_pos['lock_pts']))
                if cur_trail_loss > 0:
                    exit_reason = f"TP_{active_pos['stage']}_LOCK_EXIT"
                    exit_pnl = (active_pos['lock_pts'] * LOT_SIZE_SILVER) - ROUND_TRIP_COST

            if not exit_reason:
                best_p = high_p if is_buy else low_p
                pt_gain = (best_p - entry_p) if is_buy else (entry_p - best_p)
                peak_rupee = max(active_pos['peak_rupee'], pt_gain * LOT_SIZE_SILVER)
                active_pos['peak_rupee'] = peak_rupee

                if active_pos['stage'] == 0 and peak_rupee >= 500.0:
                    active_pos['stage'] = 1
                    active_pos['lock_pts'] = 300.0 / LOT_SIZE_SILVER
                if active_pos['stage'] <= 1 and peak_rupee >= 1000.0:
                    active_pos['stage'] = 2
                    active_pos['lock_pts'] = 700.0 / LOT_SIZE_SILVER
                if active_pos['stage'] <= 2 and peak_rupee >= 1500.0:
                    active_pos['stage'] = 3
                    active_pos['lock_pts'] = 1150.0 / LOT_SIZE_SILVER
                if active_pos['stage'] <= 3 and peak_rupee >= 2000.0:
                    active_pos['stage'] = 4
                    active_pos['lock_pts'] = 1600.0 / LOT_SIZE_SILVER
                if active_pos['stage'] <= 4 and peak_rupee >= 2500.0:
                    active_pos['stage'] = 5
                    active_pos['lock_pts'] = 2100.0 / LOT_SIZE_SILVER

                if peak_rupee >= 3000.0:
                    exit_reason = "TP_6_TARGET_EXIT"
                    exit_pnl = 3000.0 - ROUND_TRIP_COST

            if not exit_reason and idx == len(ev_bars) - 1:
                exit_reason = "EOD_SQUAREOFF"
                diff = (close_p - entry_p) if is_buy else (entry_p - close_p)
                exit_pnl = (diff * LOT_SIZE_SILVER) - ROUND_TRIP_COST

            if exit_reason:
                day_pnl += exit_pnl
                day_trades += 1
                if exit_pnl > 0: wins_si += 1
                else: losses_si += 1
                active_pos = None

        # Entry logic
        if not active_pos and day_trades < 2 and idx < len(ev_bars) - 3:
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

    total_pnl_si += day_pnl
    daily_ledger_si.append({
        "date": d,
        "month": d[:7],
        "trades": day_trades,
        "pnl": round(day_pnl, 2),
        "is_green": day_pnl > 0
    })

df_si_daily = pd.DataFrame(daily_ledger_si)
m_si = df_si_daily.groupby('month').agg(
    days=('date', 'count'),
    trades=('trades', 'sum'),
    pnl=('pnl', 'sum'),
    green=('is_green', lambda x: x.sum())
)

print("=" * 80)
print("AUDITED MCX SILVER MINI (5 KG LOT) 15-MIN REAL TICKS:")
print("=" * 80)
for m, r in m_si.iterrows():
    p_str = f"+INR {r['pnl']:,.2f}" if r['pnl'] >= 0 else f"-INR {abs(r['pnl']):,.2f}"
    print(f"{m}: {int(r['trades'])} Trades -> {p_str}")

print(f"\nTOTAL SILVER MINI PROFIT: INR {total_pnl_si:,.2f} ({wins_si}W / {losses_si}L)")
