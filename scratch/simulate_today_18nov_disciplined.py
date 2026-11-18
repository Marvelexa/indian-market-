import json
import re
import yfinance as yf
import pandas as pd
import numpy as np
import datetime

# 8-Stage Ladder matching yesterday's disciplined system
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

stock_map = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "ADANIENT": "ADANIENT.NS",
    "ADANIPORTS": "ADANIPORTS.NS",
    "APOLLOHOSP": "APOLLOHOSP.NS",
    "AXISBANK": "AXISBANK.NS",
    "BAJAJFINSV": "BAJAJFINSV.NS",
    "BAJFINANCE": "BAJFINANCE.NS",
    "BHARTIARTL": "BHARTIARTL.NS",
    "BPCL": "BPCL.NS",
    "CIPLA": "CIPLA.NS",
    "COALINDIA": "COALINDIA.NS",
    "DIVISLAB": "DIVISLAB.NS",
    "DRREDDY": "DRREDDY.NS",
    "HCLTECH": "HCLTECH.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "HINDALCO": "HINDALCO.NS",
    "HINDUNILVR": "HINDUNILVR.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "INFY": "INFY.NS",
    "IOC": "IOC.NS",
    "ITC": "ITC.NS",
    "JINDALSTEL": "JINDALSTEL.NS",
    "JSWSTEEL": "JSWSTEEL.NS",
    "KOTAKBANK": "KOTAKBANK.NS",
    "LT": "LT.NS",
    "MARUTI": "MARUTI.NS",
    "NTPC": "NTPC.NS",
    "ONGC": "ONGC.NS",
    "POWERGRID": "POWERGRID.NS",
    "RELIANCE": "RELIANCE.NS",
    "SBIN": "SBIN.NS",
    "SUNPHARMA": "SUNPHARMA.NS",
    "TATASTEEL": "TATASTEEL.NS",
    "TCS": "TCS.NS",
    "TECHM": "TECHM.NS",
    "VEDL": "VEDL.NS",
    "WIPRO": "WIPRO.NS",
}

# Real lot sizes
lot_sizes = {
    "NIFTY": 65, "BANKNIFTY": 30, "RELIANCE": 500, "HDFCBANK": 550,
    "ICICIBANK": 700, "AXISBANK": 625, "SBIN": 750, "KOTAKBANK": 2000,
    "TCS": 225, "INFY": 400, "LT": 175, "TATASTEEL": 2750, "BAJFINANCE": 750,
    "POWERGRID": 1900, "NTPC": 1500, "MARUTI": 50, "ADANIENT": 300,
    "BHARTIARTL": 475, "SUNPHARMA": 350
}

# Today's legitimate trading signals generated between 09:15 and 15:15
today_signals = [
    {"time": "09:30", "stock": "AXISBANK", "strike": 1360, "opt_type": "PE", "qty": 625, "price": 9.85},
    {"time": "09:35", "stock": "SBIN", "strike": 1110, "opt_type": "PE", "qty": 750, "price": 10.25},
    {"time": "09:42", "stock": "ICICIBANK", "strike": 1600, "opt_type": "CE", "qty": 700, "price": 9.95},
    {"time": "09:45", "stock": "LT", "strike": 4180, "opt_type": "CE", "qty": 175, "price": 37.70},
    {"time": "09:50", "stock": "HDFCBANK", "strike": 810, "opt_type": "CE", "qty": 550, "price": 5.15},
    {"time": "09:55", "stock": "BANKNIFTY", "strike": 62100, "opt_type": "CE", "qty": 30, "price": 472.35},
    {"time": "10:40", "stock": "KOTAKBANK", "strike": 495, "opt_type": "PE", "qty": 2000, "price": 4.50},
    {"time": "10:45", "stock": "NIFTY", "strike": 25250, "opt_type": "CE", "qty": 65, "price": 161.45},
    {"time": "11:00", "stock": "RELIANCE", "strike": 1360, "opt_type": "PE", "qty": 500, "price": 12.30},
    {"time": "11:19", "stock": "KOTAKBANK", "strike": 495, "opt_type": "CE", "qty": 2000, "price": 6.55},
    {"time": "11:20", "stock": "POWERGRID", "strike": 257.5, "opt_type": "CE", "qty": 1900, "price": 2.70},
    {"time": "11:27", "stock": "INFY", "strike": 1114, "opt_type": "CE", "qty": 400, "price": 12.20},
    {"time": "11:45", "stock": "LT", "strike": 4160, "opt_type": "PE", "qty": 175, "price": 36.75},
    {"time": "11:55", "stock": "TATASTEEL", "strike": 180, "opt_type": "CE", "qty": 2750, "price": 1.63},
    {"time": "12:20", "stock": "BANKNIFTY", "strike": 62200, "opt_type": "PE", "qty": 30, "price": 438.25},
    {"time": "13:15", "stock": "NIFTY", "strike": 25200, "opt_type": "PE", "qty": 65, "price": 170.00},
    {"time": "13:50", "stock": "AXISBANK", "strike": 1360, "opt_type": "CE", "qty": 625, "price": 9.85},
    {"time": "14:10", "stock": "NTPC", "strike": 317.5, "opt_type": "CE", "qty": 1500, "price": 3.80},
    {"time": "14:10", "stock": "LT", "strike": 4140, "opt_type": "CE", "qty": 175, "price": 37.70},
    {"time": "14:30", "stock": "ICICIBANK", "strike": 1600, "opt_type": "PE", "qty": 700, "price": 11.75},
    {"time": "14:35", "stock": "TATASTEEL", "strike": 180, "opt_type": "PE", "qty": 2750, "price": 2.15},
]

# Fetch yfinance 5m data for today (18-Nov-2026)
tickers = list(set([stock_map[s["stock"]] for s in today_signals]))
print(f"Downloading today (18-Nov-2026) 5m data for {len(tickers)} tickers...")
raw_data = yf.download(tickers=tickers, period="2d", interval="5m", progress=False)

def get_df_for_ticker(tick):
    if len(tickers) > 1:
        df = raw_data.xs(tick, axis=1, level=1).dropna()
    else:
        df = raw_data.dropna()
    # Filter only 18-Nov-2026
    df = df[df.index.strftime('%Y-%m-%d') == '2026-11-18']
    return df

active_positions = {}
trade_history = []

for sig in today_signals:
    ts = sig["time"]
    stock = sig["stock"]
    tick = stock_map[stock]
    
    # Check max 6 concurrent seats
    if len(active_positions) >= 6:
        continue
    if stock in active_positions:
        continue
        
    df = get_df_for_ticker(tick)
    if len(df) == 0:
        continue
        
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
print(f"\nTotal Simulated Disciplined Trades for Today (18-Nov-2026): {len(tdf)}")
print("="*120)
print(f"{'#':<3} | {'Time':<5} | {'Stock':<10} | {'Strike':<6} | {'Type':<4} | {'Qty':<5} | {'Entry ₹':<8} | {'Exit ₹':<8} | {'Exit Time':<10} | {'Max Peak':<10} | {'Realized P&L':<14} | {'Exit Reason'}")
print("="*120)
for idx, r in tdf.iterrows():
    pnl_str = f"+₹{r['pnl']:,.2f}" if r['pnl'] >= 0 else f"-₹{abs(r['pnl']):,.2f}"
    peak_str = f"+₹{r['max_reach_pnl']:,.0f}" if r['max_reach_pnl'] >= 0 else f"-₹{abs(r['max_reach_pnl']):,.0f}"
    print(f"{idx+1:<3} | {r['time']:<5} | {r['stock']:<10} | {str(r['strike']):<6} | {r['opt_type']:<4} | {r['qty']:<5} | ₹{r['entry_prem']:>6.2f} | ₹{r['exit_prem']:>6.2f} | {r['exit_time']:<10} | {peak_str:<10} | {pnl_str:<14} | {r['exit_reason']}")

print("="*120)
wins = len(tdf[tdf["pnl"] > 0])
losses = len(tdf[tdf["pnl"] < 0])
scratches = len(tdf[tdf["pnl"] == 0])
total_pnl = tdf["pnl"].sum()
win_rate = (wins / len(tdf)) * 100 if len(tdf) > 0 else 0
print(f"\n--- TODAY (18-NOV-2026) DISCIPLINED AUDIT SUMMARY ---")
print(f"Total Trades Taken : {len(tdf)}")
print(f"Winning Trades     : {wins}")
print(f"Losing Trades      : {losses}")
print(f"Win Rate           : {win_rate:.1f}%")
print(f"Total Net P&L      : ₹{total_pnl:+,.2f} ({total_pnl/100000*100:+.2f}% on ₹1,00,000 Capital)")
