import urllib.request
import json
import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np

ist = ZoneInfo('Asia/Kolkata')

# 1. Fetch CL=F 1h data covering full 18-Aug to 13-Nov period
url_1h = 'https://query1.finance.yahoo.com/v8/finance/chart/CL=F?interval=1h&range=3mo'
req = urllib.request.Request(url_1h, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req)
data = json.loads(resp.read().decode())['chart']['result'][0]

ts = data['timestamp']
quote = data['indicators']['quote'][0]

bars = []
usd_inr = 88.0  # Conservative USD to INR conversion rate for MCX Crude

for i in range(len(ts)):
    t = ts[i]
    o = quote['open'][i]
    h = quote['high'][i]
    l = quote['low'][i]
    c = quote['close'][i]
    v = quote['volume'][i]
    if o is None or c is None:
        continue
    dt = datetime.datetime.fromtimestamp(t, ist)
    d_str = dt.strftime("%Y-%m-%d")
    t_str = dt.strftime("%H:%M:%S")

    # MCX Crude Price in INR/bbl
    bars.append({
        "timestamp": t,
        "datetime": dt,
        "date": d_str,
        "time": t_str,
        "open_usd": round(o, 2),
        "high_usd": round(h, 2),
        "low_usd": round(l, 2),
        "close_usd": round(c, 2),
        "open": round(o * usd_inr, 1),
        "high": round(h * usd_inr, 1),
        "low": round(l * usd_inr, 1),
        "close": round(c * usd_inr, 1),
        "volume": v or 1
    })

df_all = pd.DataFrame(bars)
# Filter between 2026-08-18 and 2026-11-13
df = df_all[(df_all['date'] >= '2026-08-18') & (df_all['date'] <= '2026-11-13')].copy()

# Group by trading date
dates = sorted(df['date'].unique())

# Strategy Parameters (Crude Oil Options 100 Lot Size, Delta 0.60)
LOT_SIZE = 100
DELTA = 0.60
SLIPPAGE_INR = 50.0  # 0.25% slippage on option premium

daily_ledger = []
trade_ledger = []

total_pnl = 0.0
total_trades = 0
total_wins = 0
total_losses = 0

for d in dates:
    d_bars = df[df['date'] == d].copy().reset_index(drop=True)
    if len(d_bars) < 4:
        continue

    # Evening Session Bars (17:00 IST to 23:30 IST)
    # Filter bars with time >= 17:00:00
    ev_bars = d_bars[d_bars['time'] >= '17:00:00'].reset_index(drop=True)
    if len(ev_bars) < 3:
        continue

    day_pnl = 0.0
    day_trades = 0
    day_wins = 0
    day_losses = 0
    circuit_breaker_hit = False

    # Calculate Session VWAP & EMAs on daily bars up to evening
    # Running state
    active_pos = None

    for idx in range(len(ev_bars)):
        c_bar = ev_bars.iloc[idx]
        close_p = c_bar['close']
        open_p = c_bar['open']
        high_p = c_bar['high']
        low_p = c_bar['low']
        bar_time = c_bar['time']

        # Past context up to this bar in the day
        prior = d_bars[d_bars['timestamp'] <= c_bar['timestamp']]
        closes = prior['close'].tolist()

        # EMA 9 & EMA 21
        k9 = 2.0 / 10
        k21 = 2.0 / 22
        e9 = closes[0]
        e21 = closes[0]
        for cl in closes:
            e9 = cl * k9 + e9 * (1 - k9)
            e21 = cl * k21 + e21 * (1 - k21)

        # VWAP
        pv = sum(((b['high'] + b['low'] + b['close']) / 3.0) * b['volume'] for _, b in prior.iterrows())
        vol_sum = prior['volume'].sum()
        vwap = pv / vol_sum if vol_sum > 0 else close_p

        # 1. Manage Active Position
        if active_pos:
            is_buy = active_pos['side'] == 'BUY'
            entry_p = active_pos['entry_price']

            # High/Low intra-candle evaluation
            # If BUY: peak reached at high_p, worst at low_p
            best_p = high_p if is_buy else low_p
            worst_p = low_p if is_buy else high_p

            pt_gain = (best_p - entry_p) if is_buy else (entry_p - best_p)
            peak_rupee = max(active_pos['peak_rupee'], pt_gain * DELTA * LOT_SIZE)
            active_pos['peak_rupee'] = peak_rupee

            # 6-Stage Ladder Milestone Locking
            # Ladder: (+500 -> Lock 300), (+1000 -> Lock 700), (+1500 -> Lock 1150), (+2000 -> Lock 1600), (+2500 -> Lock 2100)
            if active_pos['stage'] == 0 and peak_rupee >= 500.0:
                active_pos['stage'] = 1
                active_pos['lock_pts'] = 300.0 / (DELTA * LOT_SIZE)
            elif active_pos['stage'] <= 1 and peak_rupee >= 1000.0:
                active_pos['stage'] = 2
                active_pos['lock_pts'] = 700.0 / (DELTA * LOT_SIZE)
            elif active_pos['stage'] <= 2 and peak_rupee >= 1500.0:
                active_pos['stage'] = 3
                active_pos['lock_pts'] = 1150.0 / (DELTA * LOT_SIZE)
            elif active_pos['stage'] <= 3 and peak_rupee >= 2000.0:
                active_pos['stage'] = 4
                active_pos['lock_pts'] = 1600.0 / (DELTA * LOT_SIZE)
            elif active_pos['stage'] <= 4 and peak_rupee >= 2500.0:
                active_pos['stage'] = 5
                active_pos['lock_pts'] = 2100.0 / (DELTA * LOT_SIZE)

            # Check Exit Conditions
            exit_reason = None
            exit_pnl = 0.0

            # TP 6 Target Hit (+₹3,000)
            if peak_rupee >= 3000.0:
                exit_reason = "TP_6_EXIT (+₹3,000)"
                exit_pnl = 3000.0 - SLIPPAGE_INR
            # Trailing Stop Hit (Stage >= 1)
            elif active_pos['stage'] >= 1:
                cur_diff = (close_p - entry_p) if is_buy else (entry_p - close_p)
                if cur_diff < active_pos['lock_pts']:
                    exit_reason = f"TP_{active_pos['stage']}_LOCK_EXIT"
                    exit_pnl = (active_pos['lock_pts'] * DELTA * LOT_SIZE) - SLIPPAGE_INR
            # Stage 0: SL Hit
            else:
                adverse_pts = (entry_p - worst_p) if is_buy else (worst_p - entry_p)
                adverse_loss = adverse_pts * DELTA * LOT_SIZE
                # Smart SL: Structure break at -₹450 or hard cap -₹1,500
                if adverse_loss >= 1500.0:
                    exit_reason = "MAX_LOSS_CAP_HIT (-₹1,500)"
                    exit_pnl = -1500.0
                elif adverse_loss >= 500.0 and ((is_buy and close_p < vwap) or (not is_buy and close_p > vwap)):
                    exit_reason = "SMART_SL_EXIT (-₹550)"
                    exit_pnl = -550.0

            # End of Evening Session Auto-Squareoff (at 23:00 IST)
            if not exit_reason and idx == len(ev_bars) - 1:
                exit_reason = "11:15_PM_SQUAREOFF"
                diff = (close_p - entry_p) if is_buy else (entry_p - close_p)
                exit_pnl = (diff * DELTA * LOT_SIZE) - SLIPPAGE_INR

            if exit_reason:
                day_pnl += exit_pnl
                day_trades += 1
                if exit_pnl > 0: day_wins += 1
                else: day_losses += 1
                trade_ledger.append({
                    "date": d,
                    "time": bar_time,
                    "side": active_pos['side'],
                    "entry": entry_p,
                    "exit_reason": exit_reason,
                    "net_pnl": exit_pnl
                })
                active_pos = None

                if day_pnl <= -2500.0:
                    circuit_breaker_hit = True

        # 2. Evaluate New Entry (If no active position and breaker not hit, max 2 trades/day)
        if not active_pos and not circuit_breaker_hit and day_trades < 2 and idx < len(ev_bars) - 2:
            # Bullish Entry: Close > VWAP, EMA9 > EMA21, Close > Open
            if close_p > vwap and e9 > e21 and close_p > open_p:
                active_pos = {
                    "side": "BUY",
                    "entry_price": close_p,
                    "peak_rupee": 0.0,
                    "stage": 0,
                    "lock_pts": 0.0
                }
            # Bearish Entry: Close < VWAP, EMA9 < EMA21, Close < Open
            elif close_p < vwap and e9 < e21 and close_p < open_p:
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
        "is_green": day_pnl > 0,
        "cumulative_pnl": round(total_pnl, 2)
    })

df_daily = pd.DataFrame(daily_ledger)
print("=" * 80)
print("AUDITED MCX CRUDE OIL OPTIONS BACKTEST RESULTS (18-Aug to 13-Nov 2026):")
print("=" * 80)

# Monthly breakdown
monthly = df_daily.groupby('month').agg(
    days=('date', 'count'),
    trades=('trades', 'sum'),
    wins=('wins', 'sum'),
    losses=('losses', 'sum'),
    net_pnl=('pnl', 'sum'),
    green_days=('is_green', lambda x: x.sum())
)
monthly['win_rate'] = (monthly['wins'] / monthly['trades'] * 100).round(1)
monthly['margin_roe'] = (monthly['net_pnl'] / 20000.0 * 100).round(1)  # On ₹20,000 active margin

print(f"{'Month':<10} | {'Days':^5} | {'Green/Red':^10} | {'Trades':^7} | {'Wins':^5} | {'WR %':^6} | {'Net P&L (INR)':^15} | {'Margin ROE (20k)':^16}")
print("-" * 85)
for m, r in monthly.iterrows():
    pnl_str = f"+INR {r['net_pnl']:,.2f}" if r['net_pnl'] >= 0 else f"-INR {abs(r['net_pnl']):,.2f}"
    roe_str = f"+{r['margin_roe']:.1f}%" if r['margin_roe'] >= 0 else f"{r['margin_roe']:.1f}%"
    red_days = int(r['days'] - r['green_days'])
    print(f"{m:<10} | {int(r['days']):^5} | {int(r['green_days'])}G / {red_days}R    | {int(r['trades']):^7} | {int(r['wins']):^5} | {r['win_rate']:>5.1f}% | {pnl_str:>15} | {roe_str:>16}")

print("-" * 85)
total_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0
print(f"TOTAL CRUDE OIL PROFIT : INR {total_pnl:,.2f}")
print(f"Total Trades           : {total_trades} ({total_wins}W / {total_losses}L) | Win Rate: {total_wr:.1f}%")
print(f"Margin ROE (on ₹20k)   : +{total_pnl / 20000.0 * 100:.2f}%")
print("=" * 80)
