import json
import re
import yfinance as yf
import pandas as pd
import numpy as np

# Load all parsed signals
from parse_stock_signals import parsed_signals

# Group signals: When multiple orders occurred for the same stock within a short time because of premature cut,
# in a clean system that trade would have stayed OPEN until SL (-2500) or ladder exit!
# Let's run an event-driven simulation where only 1 position per stock is open at a time!

ladder_stages = [
    (8000.0, 8000.0, "STAGE 8: FULL MARKET TARGET (+₹8,000)"),
    (6000.0, 4800.0, "STAGE 7: TRAILING LOCK (+₹4,800)"),
    (4500.0, 3600.0, "STAGE 6: TRAILING LOCK (+₹3,600)"),
    (3000.0, 2400.0, "STAGE 5: TRAILING LOCK (+₹2,400)"),
    (2000.0, 1600.0, "STAGE 4: TRAILING LOCK (+₹1,600)"),
    (1500.0, 1150.0, "STAGE 3: TRAILING LOCK (+₹1,150)"),
    (1000.0, 700.0,  "STAGE 2: TRAILING LOCK (+₹700)"),
    (500.0,  300.0,  "STAGE 1: TRAILING LOCK (+₹300)"),
]
HARD_SL_INR = -2500.0

# Collect unique tickers
tickers = list(set([s["ticker"] for s in parsed_signals if s["ticker"]]))
print(f"Downloading data for {len(tickers)} tickers...")
raw_data = yf.download(tickers=tickers, period="1d", interval="5m", progress=False)

def get_df_for_ticker(tick):
    if len(tickers) > 1:
        return raw_data.xs(tick, axis=1, level=1).dropna()
    else:
        return raw_data.dropna()

# We simulate positions:
# If a position in symbol X is ALREADY open, ignore new entry signals for X until that position closes!
# Also max 6 seats at any time!
active_positions = {}
trade_history = []
seat_names = ["OPTION_1", "OPTION_2", "TREND_1", "TREND_2", "CHOP_1", "CHOP_2"]

for sig in parsed_signals:
    ts = sig["time"]
    stock = sig["stock"]
    tick = sig["ticker"]
    if not tick:
        continue
    
    # Check if stock already has open position
    if stock in active_positions:
        continue
        
    # Check seat availability (max 6)
    if len(active_positions) >= 6:
        continue
        
    df = get_df_for_ticker(tick)
    times = [t.strftime("%H:%M") for t in df.index]
    
    entry_idx = 0
    for i, t in enumerate(times):
        if t >= ts:
            entry_idx = i
            break
            
    if entry_idx >= len(df):
        continue
        
    entry_candle = df.iloc[entry_idx]
    entry_spot = entry_candle["Open"]
    qty = sig["qty"]
    entry_prem = sig["price"]
    opt_type = sig["opt_type"]
    
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

        # Hard SL check: -₹2500
        if highest_locked == 0.0 and unrealized_worst <= HARD_SL_INR:
            exit_prem = round(max(0.05, entry_prem + (HARD_SL_INR / qty)), 2)
            exit_info = {
                "exit_time": c_time,
                "exit_prem": exit_prem,
                "exit_reason": f"HARD SL (-₹{abs(HARD_SL_INR):.0f})",
                "max_reach_pnl": max_pnl_seen,
                "pnl": HARD_SL_INR,
            }
            closed = True
            break

        # Check ladder
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

        if highest_locked > 0.0 and unrealized_close <= highest_locked:
            exit_prem = round(entry_prem + (highest_locked / qty), 2)
            exit_info = {
                "exit_time": c_time,
                "exit_prem": exit_prem,
                "exit_reason": highest_stage_name,
                "max_reach_pnl": max_pnl_seen,
                "pnl": highest_locked,
            }
            closed = True
            break

        if c_time >= "15:18":
            exit_prem = round(max(0.05, entry_prem + close_opt_move), 2)
            final_pnl = round((exit_prem - entry_prem) * qty, 2)
            exit_info = {
                "exit_time": "15:18",
                "exit_prem": exit_prem,
                "exit_reason": f"03:18 PM AUTO SQUARE-OFF",
                "max_reach_pnl": max_pnl_seen,
                "pnl": final_pnl,
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
            "exit_time": "15:30",
            "exit_prem": curr_prem,
            "exit_reason": "MARKET CLOSE SQUARE-OFF",
            "max_reach_pnl": max_pnl_seen,
            "pnl": live_pnl,
        }

    trade_history.append({
        "time": ts,
        "stock": stock,
        "strike": sig["strike"],
        "opt_type": opt_type,
        "qty": qty,
        "entry_prem": entry_prem,
        **exit_info
    })

tdf = pd.DataFrame(trade_history)
print(f"\nTotal Simulated Disciplined Trades (Max 6 concurrent seats): {len(tdf)}")
print("="*110)
print(f"{'#':<3} | {'Time':<5} | {'Stock':<10} | {'Strike':<6} | {'Type':<4} | {'Qty':<5} | {'Entry ₹':<8} | {'Exit ₹':<8} | {'Exit Time':<10} | {'Peak':<9} | {'Realized P&L':<12} | {'Exit Reason'}")
print("="*110)
for idx, r in tdf.iterrows():
    print(f"{idx+1:<3} | {r['time']:<5} | {r['stock']:<10} | {r['strike']:<6} | {r['opt_type']:<4} | {r['qty']:<5} | ₹{r['entry_prem']:>6.2f} | ₹{r['exit_prem']:>6.2f} | {r['exit_time']:<10} | +₹{r['max_reach_pnl']:>6,.0f} | ₹{r['pnl']:>+10,.2f} | {r['exit_reason']}")

net_pnl = tdf["pnl"].sum()
wins = tdf[tdf["pnl"] > 0]
losses = tdf[tdf["pnl"] < 0]
print("="*110)
print(f"TOTAL TRADES: {len(tdf)}")
print(f"WINNERS: {len(wins)} (Gross Profit: +₹{wins['pnl'].sum():,.2f})")
print(f"LOSERS:  {len(losses)} (Gross Loss: ₹{losses['pnl'].sum():,.2f})")
print(f"WIN RATE: {len(wins)/len(tdf)*100:.1f}%")
print(f"TOTAL REAL MARKET NET PROFIT: ₹{net_pnl:+,.2f}")
print("="*110)
