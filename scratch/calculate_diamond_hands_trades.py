import yfinance as yf
import pandas as pd
import numpy as np

# Trades list from morning blotter
trades_list = [
    # 1. Morning batch (09:17 - 09:30)
    {"id": "TRD-01", "time": "09:17", "symbol": "ADANIENT", "strike": 2680, "type": "CE", "qty": 300, "entry_prem": 58.93, "ticker": "ADANIENT.NS", "is_index": False},
    {"id": "TRD-02", "time": "09:23", "symbol": "ONGC", "strike": 225, "type": "PE", "qty": 3850, "entry_prem": 4.95, "ticker": "ONGC.NS", "is_index": False},
    {"id": "TRD-03", "time": "09:24", "symbol": "HINDALCO", "strike": 930, "type": "CE", "qty": 1400, "entry_prem": 20.42, "ticker": "HINDALCO.NS", "is_index": False},
    {"id": "TRD-04", "time": "09:24", "symbol": "VEDL", "strike": 255, "type": "CE", "qty": 1150, "entry_prem": 5.59, "ticker": "VEDL.NS", "is_index": False},
    {"id": "TRD-05", "time": "09:25", "symbol": "SBIN", "strike": 1100, "type": "CE", "qty": 750, "entry_prem": 24.16, "ticker": "SBIN.NS", "is_index": False},
    {"id": "TRD-06", "time": "09:26", "symbol": "NTPC", "strike": 320, "type": "PE", "qty": 1500, "entry_prem": 7.05, "ticker": "NTPC.NS", "is_index": False},
    {"id": "TRD-07", "time": "09:27", "symbol": "DIVISLAB", "strike": 11100, "type": "CE", "qty": 100, "entry_prem": 244.66, "ticker": "DIVISLAB.NS", "is_index": False},
    {"id": "TRD-08", "time": "09:30", "symbol": "NIFTY", "strike": 25300, "type": "CE", "qty": 75, "entry_prem": 180.00, "ticker": "^NSEI", "is_index": True},
    {"id": "TRD-09", "time": "09:30", "symbol": "BANKNIFTY", "strike": 61700, "type": "CE", "qty": 30, "entry_prem": 380.00, "ticker": "^NSEBANK", "is_index": True},
    {"id": "TRD-10", "time": "09:30", "symbol": "AXISBANK", "strike": 1360, "type": "CE", "qty": 625, "entry_prem": 29.79, "ticker": "AXISBANK.NS", "is_index": False},

    # 2. Rows 11, 12, 13 (Previously cut at +₹165, +₹304, -₹550 under "Quick Scalp Exit")
    {"id": "TRD-11", "time": "09:40", "symbol": "HDFCBANK", "strike": 810, "type": "CE", "qty": 550, "entry_prem": 17.86, "ticker": "HDFCBANK.NS", "is_index": False},
    {"id": "TRD-12", "time": "09:41", "symbol": "LT", "strike": 4150, "type": "PE", "qty": 150, "entry_prem": 91.30, "ticker": "LT.NS", "is_index": False},
    {"id": "TRD-13", "time": "09:43", "symbol": "AXISBANK", "strike": 1350, "type": "PE", "qty": 625, "entry_prem": 29.74, "ticker": "AXISBANK.NS", "is_index": False},

    # 3. Re-entries & Continuation
    {"id": "TRD-14", "time": "10:03", "symbol": "NIFTY", "strike": 25350, "type": "CE", "qty": 75, "entry_prem": 180.00, "ticker": "^NSEI", "is_index": True},
    {"id": "TRD-15", "time": "10:03", "symbol": "BANKNIFTY", "strike": 62100, "type": "CE", "qty": 30, "entry_prem": 380.00, "ticker": "^NSEBANK", "is_index": True},
    {"id": "TRD-16", "time": "10:03", "symbol": "HCLTECH", "strike": 1380, "type": "PE", "qty": 350, "entry_prem": 30.22, "ticker": "HCLTECH.NS", "is_index": False},
    {"id": "TRD-17", "time": "10:56", "symbol": "ICICIBANK", "strike": 1600, "type": "PE", "qty": 700, "entry_prem": 35.41, "ticker": "ICICIBANK.NS", "is_index": False},
    {"id": "TRD-18", "time": "11:04", "symbol": "JINDALSTEL", "strike": 1130, "type": "PE", "qty": 625, "entry_prem": 25.00, "ticker": "JINDALSTEL.NS", "is_index": False},
    {"id": "TRD-19", "time": "11:09", "symbol": "JINDALSTEL", "strike": 1140, "type": "CE", "qty": 625, "entry_prem": 25.00, "ticker": "JINDALSTEL.NS", "is_index": False},
    {"id": "TRD-20", "time": "11:17", "symbol": "TATASTEEL", "strike": 182.5, "type": "PE", "qty": 2750, "entry_prem": 4.00, "ticker": "TATASTEEL.NS", "is_index": False},
    {"id": "TRD-21", "time": "11:22", "symbol": "JSWSTEEL", "strike": 1330, "type": "PE", "qty": 675, "entry_prem": 29.33, "ticker": "JSWSTEEL.NS", "is_index": False},
    {"id": "TRD-22", "time": "11:25", "symbol": "DIVISLAB", "strike": 11050, "type": "PE", "qty": 100, "entry_prem": 243.63, "ticker": "DIVISLAB.NS", "is_index": False},
    {"id": "TRD-23", "time": "11:26", "symbol": "TATASTEEL", "strike": 182.5, "type": "CE", "qty": 2750, "entry_prem": 4.02, "ticker": "TATASTEEL.NS", "is_index": False},
]

tickers = list(set([t["ticker"] for t in trades_list]))
raw_data = yf.download(tickers=tickers, period="1d", interval="5m", progress=False)

results = []

def evaluate_diamond_hands_trade(trd, df, times):
    entry_time_str = trd["time"]
    qty = trd["qty"]
    entry_prem = trd["entry_prem"]
    opt_type = trd["type"]
    delta = 0.55

    entry_idx = 0
    for i, t in enumerate(times):
        if t >= entry_time_str:
            entry_idx = i
            break
            
    entry_candle = df.iloc[entry_idx]
    entry_spot = entry_candle["Open"]

    peak_pnl = 0.0
    ladder_stage = 0
    locked_pnl = 0.0

    for i in range(entry_idx, len(df)):
        c_time = times[i]
        c = df.iloc[i]
        hold_minutes = (i - entry_idx) * 5

        # Check 03:18 PM mandatory square-off
        if c_time >= "15:18":
            close_spot = c["Close"]
            gain_pts = (close_spot - entry_spot if opt_type == "CE" else entry_spot - close_spot) * delta
            exit_prem = round(max(0.05, entry_prem + gain_pts), 2)
            pnl = round((exit_prem - entry_prem) * qty, 2)
            return {
                **trd,
                "entry_spot": round(entry_spot, 2),
                "exit_time": c_time,
                "exit_prem": exit_prem,
                "exit_reason": "03:18 PM AUTO SQUARE-OFF",
                "pnl": pnl,
                "hold_minutes": hold_minutes,
                "ladder_stage": ladder_stage
            }

        # Worst and Best in candle
        if opt_type == "CE":
            best_spot = c["High"]
            worst_spot = c["Low"]
            close_spot = c["Close"]
        else:
            best_spot = c["Low"]
            worst_spot = c["High"]
            close_spot = c["Close"]

        best_gain = (best_spot - entry_spot if opt_type == "CE" else entry_spot - best_spot) * delta
        worst_loss = (worst_spot - entry_spot if opt_type == "CE" else entry_spot - worst_spot) * delta
        close_move = (close_spot - entry_spot if opt_type == "CE" else entry_spot - close_spot) * delta

        unrealized_peak = round(best_gain * qty, 2)
        unrealized_trough = round(worst_loss * qty, 2)
        unrealized_close = round(close_move * qty, 2)

        peak_pnl = max(peak_pnl, unrealized_peak)

        # 1. Hard Stop Loss (-₹2,500 Breathing Room Guarantee)
        if unrealized_trough <= -2500.0:
            exit_prem = round(max(0.05, entry_prem - (2500.0 / qty)), 2)
            return {
                **trd,
                "entry_spot": round(entry_spot, 2),
                "exit_time": c_time,
                "exit_prem": exit_prem,
                "exit_reason": "HARD SL (-₹2,500 Cap)",
                "pnl": -2500.0,
                "hold_minutes": hold_minutes,
                "ladder_stage": ladder_stage
            }

        # 2. Diamond-Hands Breathing Ladder
        # Below +₹1,500 PnL: 100% HANDS-OFF HOLD (Zero premature exits!)
        if peak_pnl >= 6000.0:
            ladder_stage = 4
            locked_pnl = max(4500.0, peak_pnl - 1400.0)
        elif peak_pnl >= 4000.0 and ladder_stage < 3:
            ladder_stage = 3
            locked_pnl = 2800.0
        elif peak_pnl >= 2500.0 and ladder_stage < 2:
            ladder_stage = 2
            locked_pnl = 1650.0
        elif peak_pnl >= 1500.0 and ladder_stage < 1:
            ladder_stage = 1
            locked_pnl = 850.0

        # Trailing SL Trigger
        if locked_pnl > 0 and unrealized_trough <= locked_pnl and hold_minutes >= 10:
            exit_prem = round(entry_prem + (locked_pnl / qty), 2)
            return {
                **trd,
                "entry_spot": round(entry_spot, 2),
                "exit_time": c_time,
                "exit_prem": exit_prem,
                "exit_reason": f"DIAMOND_HANDS_STAGE_{ladder_stage}_LOCKED (+₹{int(locked_pnl)})",
                "pnl": locked_pnl,
                "hold_minutes": hold_minutes,
                "ladder_stage": ladder_stage
            }

    # If held till end of day
    last_c = df.iloc[-1]
    last_spot = last_c["Close"]
    gain_pts = (last_spot - entry_spot if opt_type == "CE" else entry_spot - last_spot) * delta
    exit_prem = round(max(0.05, entry_prem + gain_pts), 2)
    pnl = round((exit_prem - entry_prem) * qty, 2)
    return {
        **trd,
        "entry_spot": round(entry_spot, 2),
        "exit_time": times[-1],
        "exit_prem": exit_prem,
        "exit_reason": "EOD_HOLD",
        "pnl": pnl,
        "hold_minutes": len(df) * 5,
        "ladder_stage": ladder_stage
    }

for trd in trades_list:
    tick = trd["ticker"]
    if len(tickers) > 1:
        df = raw_data.xs(tick, axis=1, level=1).dropna()
    else:
        df = raw_data.dropna()
    times = [t.strftime("%H:%M") for t in df.index]
    res = evaluate_diamond_hands_trade(trd, df, times)
    results.append(res)

print("=" * 95)
print("💎 DIAMOND-HANDS AUDIT: ROWS 11, 12, 13 & FULL PORTFOLIO HOLD RESULTS")
print("=" * 95)
print(f"{'ID':<7} | {'SYMBOL':<10} | {'STRIKE':<8} | {'TYPE':<4} | {'ENTRY':<6} | {'EXIT':<6} | {'TIME HELD':<10} | {'EXIT REASON':<32} | {'NET PNL (INR)':<12}")
print("-" * 95)

total_pnl = 0.0
wins = 0
losses = 0

for r in results:
    total_pnl += r["pnl"]
    if r["pnl"] > 0: wins += 1
    elif r["pnl"] < 0: losses += 1
    is_target_row = r["id"] in ["TRD-11", "TRD-12", "TRD-13"]
    highlight = "🔥 " if is_target_row else "   "
    print(f"{highlight}{r['id']:<5} | {r['symbol']:<10} | {r['strike']:<8} | {r['type']:<4} | {r['time']} | {r['exit_time']} | {str(r['hold_minutes'])+'m':<10} | {r['exit_reason']:<32} | +₹{r['pnl']:<10.2f}" if r['pnl'] >= 0 else f"{highlight}{r['id']:<5} | {r['symbol']:<10} | {r['strike']:<8} | {r['type']:<4} | {r['time']} | {r['exit_time']} | {str(r['hold_minutes'])+'m':<10} | {r['exit_reason']:<32} | -₹{abs(r['pnl']):<10.2f}")

print("=" * 95)
print(f"TOTAL REAL MARKET PNL (DIAMOND HANDS): +₹{total_pnl:,.2f}")
print(f"TOTAL TRADES: {len(results)} | WINS: {wins} | LOSSES: {losses} | WIN RATE: {round(wins/len(results)*100, 1)}%")
print("=" * 95)
