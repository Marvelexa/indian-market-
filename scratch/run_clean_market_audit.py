import yfinance as yf
import pandas as pd
import numpy as np

# Let's run the exact simulation on all legitimate trades with real NSE 5m candles
from ladder_8stage_sl2500 import trades_list, ladder_stages, HARD_SL_INR

tickers = list(set([t["ticker"] for t in trades_list]))
print(f"Downloading 5m candles for {len(tickers)} tickers...")
raw_data = yf.download(tickers=tickers, period="1d", interval="5m", progress=False)

results = []

for trd in trades_list:
    tick = trd["ticker"]
    qty = trd["qty"]
    entry_prem = trd["entry_prem"]
    opt_type = trd["type"]
    entry_time_str = trd["time"]
    
    if len(tickers) > 1:
        df = raw_data.xs(tick, axis=1, level=1).dropna()
    else:
        df = raw_data.dropna()

    times = [t.strftime("%H:%M") for t in df.index]
    entry_idx = 0
    for i, t in enumerate(times):
        if t >= entry_time_str:
            entry_idx = i
            break
            
    entry_candle = df.iloc[entry_idx]
    entry_spot = entry_candle["Open"]
    
    # Simulate candle-by-candle from entry using Diamond Hands hold rules

    delta = 0.55
    closed = False
    exit_info = None

    max_pnl_seen = 0.0
    highest_locked = 0.0
    highest_stage_name = None

    for i in range(entry_idx, len(df)):
        c_time = times[i]
        c = df.iloc[i]

        if opt_type == "CE":
            best_spot = c["High"]
            worst_spot = c["Low"]
            close_spot = c["Close"]
        else:
            best_spot = c["Low"]
            worst_spot = c["High"]
            close_spot = c["Close"]

        best_opt_gain = (best_spot - entry_spot if opt_type == "CE" else entry_spot - best_spot) * delta
        worst_opt_loss = (worst_spot - entry_spot if opt_type == "CE" else entry_spot - worst_spot) * delta
        close_opt_move = (close_spot - entry_spot if opt_type == "CE" else entry_spot - close_spot) * delta

        unrealized_best = round(best_opt_gain * qty, 2)
        unrealized_worst = round(worst_opt_loss * qty, 2)
        unrealized_close = round(close_opt_move * qty, 2)

        if unrealized_best > max_pnl_seen:
            max_pnl_seen = unrealized_best

        # Hard SL check: Strictly -₹2500!
        if highest_locked == 0.0 and unrealized_worst <= HARD_SL_INR:
            exit_prem = round(max(0.05, entry_prem + (HARD_SL_INR / qty)), 2)
            exit_info = {
                "exit_time": c_time,
                "exit_prem": exit_prem,
                "exit_reason": f"HARD SL (-₹{abs(HARD_SL_INR):.0f})",
                "max_reach_pnl": max_pnl_seen,
                "pnl": HARD_SL_INR,
                "status": "CLOSED"
            }
            closed = True
            break

        # Check Stage ladder triggers
        for trig, lock_val, stage_name in ladder_stages:
            if unrealized_best >= trig:
                if trig == 8000.0:
                    exit_prem = round(entry_prem + (8000.0 / qty), 2)
                    exit_info = {
                        "exit_time": c_time,
                        "exit_prem": exit_prem,
                        "exit_reason": stage_name,
                        "max_reach_pnl": max_pnl_seen,
                        "pnl": 8000.0,
                        "status": "CLOSED"
                    }
                    closed = True
                    break
                else:
                    if lock_val > highest_locked:
                        highest_locked = lock_val
                        highest_stage_name = stage_name
                break
        
        if closed:
            break

        # Check trailing lock breach
        if highest_locked > 0.0 and unrealized_close <= highest_locked:
            exit_prem = round(entry_prem + (highest_locked / qty), 2)
            exit_info = {
                "exit_time": c_time,
                "exit_prem": exit_prem,
                "exit_reason": highest_stage_name,
                "max_reach_pnl": max_pnl_seen,
                "pnl": highest_locked,
                "status": "CLOSED"
            }
            closed = True
            break

        # At 15:18 / end of day auto square-off
        if c_time >= "15:18":
            exit_prem = round(max(0.05, entry_prem + close_opt_move), 2)
            final_pnl = round((exit_prem - entry_prem) * qty, 2)
            exit_info = {
                "exit_time": "15:18 (AUTO CLOSE)",
                "exit_prem": exit_prem,
                "exit_reason": f"03:18 PM AUTO SQUARE-OFF (Max reached +₹{max_pnl_seen:,.0f})",
                "max_reach_pnl": max_pnl_seen,
                "pnl": final_pnl,
                "status": "CLOSED"
            }
            closed = True
            break

    if not closed:
        last_c = df.iloc[-1]
        last_spot = last_c["Close"]
        last_move = (last_spot - entry_spot if opt_type == "CE" else entry_spot - last_spot) * delta
        curr_prem = round(max(0.05, entry_prem + last_move), 2)
        live_pnl = round((curr_prem - entry_prem) * qty, 2)
        exit_info = {
            "exit_time": "15:30 (MKT CLOSE)",
            "exit_prem": curr_prem,
            "exit_reason": f"MARKET CLOSE SQUARE-OFF (Max reached +₹{max_pnl_seen:,.0f})",
            "max_reach_pnl": max_pnl_seen,
            "pnl": live_pnl,
            "status": "CLOSED"
        }

    results.append({
        **trd,
        "entry_spot": round(entry_spot, 2),
        **exit_info
    })

res_df = pd.DataFrame(results)

print("\n" + "="*110)
print(f"{'#':<3} | {'Time':<5} | {'Symbol':<10} | {'Strike':<6} | {'Type':<4} | {'Qty':<5} | {'Entry ₹':<8} | {'Exit ₹':<8} | {'Exit Time':<10} | {'Max Peak':<10} | {'Realized P&L':<12} | {'Exit Reason'}")
print("="*110)
for idx, r in res_df.iterrows():
    print(f"{idx+1:<3} | {r['time']:<5} | {r['symbol']:<10} | {r['strike']:<6} | {r['type']:<4} | {r['qty']:<5} | ₹{r['entry_prem']:>6.2f} | ₹{r['exit_prem']:>6.2f} | {r['exit_time']:<10} | +₹{r['max_reach_pnl']:>7,.0f} | ₹{r['pnl']:>+10,.2f} | {r['exit_reason']}")

total_net = res_df["pnl"].sum()
wins = res_df[res_df["pnl"] > 0]
losses = res_df[res_df["pnl"] < 0]
print("\n" + "="*110)
print(f"TOTAL LEGITIMATE TRADES: {len(res_df)}")
print(f"WINNERS: {len(wins)} (Gross Profit: +₹{wins['pnl'].sum():,.2f})")
print(f"LOSERS:  {len(losses)} (Gross Loss: ₹{losses['pnl'].sum():,.2f})")
print(f"WIN RATE: {len(wins)/len(res_df)*100:.1f}%")
print(f"TOTAL REAL MARKET PROFIT (Clean ₹2,500 SL & 8-Stage Ladder): ₹{total_net:+,.2f}")
print("="*110)
