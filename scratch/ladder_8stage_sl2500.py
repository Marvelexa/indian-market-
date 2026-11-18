import yfinance as yf
import pandas as pd
import numpy as np

# Trades list from morning blotter & screenshots
trades_list = [
    # 1. Morning batch (09:17 - 09:30)
    {"id": "TRD-01", "time": "09:17", "symbol": "ADANIENT", "strike": 2680, "type": "CE", "qty": 300, "entry_prem": 58.93, "ticker": "ADANIENT.NS"},
    {"id": "TRD-02", "time": "09:23", "symbol": "ONGC", "strike": 225, "type": "PE", "qty": 3850, "entry_prem": 4.95, "ticker": "ONGC.NS"},
    {"id": "TRD-03", "time": "09:24", "symbol": "HINDALCO", "strike": 930, "type": "CE", "qty": 1400, "entry_prem": 20.42, "ticker": "HINDALCO.NS"},
    {"id": "TRD-04", "time": "09:24", "symbol": "VEDL", "strike": 255, "type": "CE", "qty": 1150, "entry_prem": 5.59, "ticker": "VEDL.NS"},
    {"id": "TRD-05", "time": "09:25", "symbol": "SBIN", "strike": 1100, "type": "CE", "qty": 750, "entry_prem": 24.16, "ticker": "SBIN.NS"},
    {"id": "TRD-06", "time": "09:26", "symbol": "NTPC", "strike": 320, "type": "PE", "qty": 1500, "entry_prem": 7.05, "ticker": "NTPC.NS"},
    {"id": "TRD-07", "time": "09:27", "symbol": "DIVISLAB", "strike": 11100, "type": "CE", "qty": 100, "entry_prem": 244.66, "ticker": "DIVISLAB.NS"},
    {"id": "TRD-08", "time": "09:30", "symbol": "NIFTY", "strike": 25300, "type": "CE", "qty": 75, "entry_prem": 180.00, "ticker": "^NSEI"},
    {"id": "TRD-09", "time": "09:30", "symbol": "BANKNIFTY", "strike": 61700, "type": "CE", "qty": 30, "entry_prem": 380.00, "ticker": "^NSEBANK"},
    {"id": "TRD-10", "time": "09:30", "symbol": "AXISBANK", "strike": 1360, "type": "CE", "qty": 625, "entry_prem": 29.79, "ticker": "AXISBANK.NS"},

    # 2. Rows 11, 12, 13 (Diamond-Hands Breathing Hold)
    {"id": "TRD-11", "time": "09:40", "symbol": "HDFCBANK", "strike": 810, "type": "CE", "qty": 550, "entry_prem": 17.86, "ticker": "HDFCBANK.NS"},
    {"id": "TRD-12", "time": "09:41", "symbol": "LT", "strike": 4150, "type": "PE", "qty": 150, "entry_prem": 91.30, "ticker": "LT.NS"},
    {"id": "TRD-13", "time": "09:43", "symbol": "AXISBANK", "strike": 1350, "type": "PE", "qty": 625, "entry_prem": 29.74, "ticker": "AXISBANK.NS"},

    # 3. 10:03 - 11:30 Re-entries & Index Rolls
    {"id": "TRD-14", "time": "10:03", "symbol": "NIFTY", "strike": 25350, "type": "CE", "qty": 75, "entry_prem": 180.00, "ticker": "^NSEI"},
    {"id": "TRD-15", "time": "10:03", "symbol": "BANKNIFTY", "strike": 62100, "type": "CE", "qty": 30, "entry_prem": 380.00, "ticker": "^NSEBANK"},
    {"id": "TRD-16", "time": "10:03", "symbol": "HCLTECH", "strike": 1380, "type": "PE", "qty": 350, "entry_prem": 30.22, "ticker": "HCLTECH.NS"},
    {"id": "TRD-17", "time": "10:56", "symbol": "ICICIBANK", "strike": 1600, "type": "PE", "qty": 700, "entry_prem": 35.41, "ticker": "ICICIBANK.NS"},
    {"id": "TRD-18", "time": "11:04", "symbol": "JINDALSTEL", "strike": 1130, "type": "PE", "qty": 625, "entry_prem": 25.00, "ticker": "JINDALSTEL.NS"},
    {"id": "TRD-19", "time": "11:09", "symbol": "JINDALSTEL", "strike": 1140, "type": "CE", "qty": 625, "entry_prem": 25.00, "ticker": "JINDALSTEL.NS"},
    {"id": "TRD-20", "time": "11:17", "symbol": "TATASTEEL", "strike": 182, "type": "PE", "qty": 5500, "entry_prem": 4.00, "ticker": "TATASTEEL.NS"},
    {"id": "TRD-21", "time": "11:22", "symbol": "JSWSTEEL", "strike": 1330, "type": "PE", "qty": 675, "entry_prem": 29.33, "ticker": "JSWSTEEL.NS"},
    {"id": "TRD-22", "time": "11:25", "symbol": "DIVISLAB", "strike": 11050, "type": "PE", "qty": 100, "entry_prem": 243.63, "ticker": "DIVISLAB.NS"},
    {"id": "TRD-23", "time": "11:26", "symbol": "TATASTEEL", "strike": 183, "type": "CE", "qty": 5500, "entry_prem": 4.02, "ticker": "TATASTEEL.NS"},
]

tickers = list(set([t["ticker"] for t in trades_list]))
raw_data = yf.download(tickers=tickers, period="1d", interval="5m", progress=False)

# 8-Stage Ladder from AGENTS.md Section 3:
# Stage 1: +500 -> Lock +300
# Stage 2: +1000 -> Lock +700
# Stage 3: +1500 -> Lock +1150
# Stage 4: +2000 -> Lock +1600
# Stage 5: +3000 -> Lock +2400
# Stage 6: +4500 -> Lock +3600
# Stage 7: +6000 -> Lock +4800
# Stage 8: +8000 -> Full Target Exit

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

HARD_SL_INR = -2500.0  # As user specified: ₹2500 per lot!

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
    
    # Simulate candle-by-candle from entry using Diamond Hands Hold Rules

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
                "exit_reason": f"03:18 PM AUTO SQUARE-OFF (Max was +₹{max_pnl_seen:,.0f})" if max_pnl_seen > 0 else "03:18 PM AUTO SQUARE-OFF",
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
            "exit_reason": f"MARKET CLOSE SQUARE-OFF (Max was +₹{max_pnl_seen:,.0f})",
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
print("\n" + "="*85)
print("AUDIT WITH ₹2,500 HARD SL & EXACT 8-STAGE EXTENDED LADDER (UP TO ₹8,000)")
print("="*85)
for idx, r in res_df.iterrows():
    print(f"[{r['time']}] {r['symbol']:<10} {r['strike']} {r['type']:<2} | Entry ₹{r['entry_prem']:>6.2f} -> Exit ₹{r['exit_prem']:>6.2f} [{r['exit_time']}] | Max Reach: +₹{r['max_reach_pnl']:>7,.0f} | Realized PnL: ₹{r['pnl']:>+8,.2f} | {r['exit_reason']}")

total_net = res_df["pnl"].sum()
wins = res_df[res_df["pnl"] > 0]
losses = res_df[res_df["pnl"] < 0]
print("\n" + "-"*85)
print(f"TOTAL TRADES: {len(res_df)}")
print(f"WINNING TRADES: {len(wins)} (Gross Profit: +₹{wins['pnl'].sum():,.2f})")
print(f"LOSING TRADES:  {len(losses)} (Gross Loss: ₹{losses['pnl'].sum():,.2f})")
print(f"WIN RATE: {len(wins)/len(res_df)*100:.1f}%")
print(f"FINAL NET REAL MARKET PROFIT: ₹{total_net:+,.2f}")
print(f"RETURN ON ₹1,00,000 CAPITAL: {total_net/100000*100:+.2f}%")
print("-"*85)
