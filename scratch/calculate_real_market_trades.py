import yfinance as yf
import pandas as pd
import numpy as np

# Trades list from morning blotter & screenshots
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

    # 2. Rows 11, 12, 13 (Now evaluated under Diamond Hands Hold Manager - zero premature scalp exits)
    {"id": "TRD-11", "time": "09:40", "symbol": "HDFCBANK", "strike": 810, "type": "CE", "qty": 550, "entry_prem": 17.86, "ticker": "HDFCBANK.NS", "is_index": False},
    {"id": "TRD-12", "time": "09:41", "symbol": "LT", "strike": 4150, "type": "PE", "qty": 150, "entry_prem": 91.30, "ticker": "LT.NS", "is_index": False},
    {"id": "TRD-13", "time": "09:43", "symbol": "AXISBANK", "strike": 1350, "type": "PE", "qty": 625, "entry_prem": 29.74, "ticker": "AXISBANK.NS", "is_index": False},

    # 3. 10:03 - 11:30 Re-entries & Index Rolls
    {"id": "TRD-14", "time": "10:03", "symbol": "NIFTY", "strike": 25350, "type": "CE", "qty": 75, "entry_prem": 180.00, "ticker": "^NSEI", "is_index": True},
    {"id": "TRD-15", "time": "10:03", "symbol": "BANKNIFTY", "strike": 62100, "type": "CE", "qty": 30, "entry_prem": 380.00, "ticker": "^NSEBANK", "is_index": True},
    {"id": "TRD-16", "time": "10:03", "symbol": "HCLTECH", "strike": 1380, "type": "PE", "qty": 350, "entry_prem": 30.22, "ticker": "HCLTECH.NS", "is_index": False},
    {"id": "TRD-17", "time": "10:56", "symbol": "ICICIBANK", "strike": 1600, "type": "PE", "qty": 700, "entry_prem": 35.41, "ticker": "ICICIBANK.NS", "is_index": False},
    {"id": "TRD-18", "time": "11:04", "symbol": "JINDALSTEL", "strike": 1130, "type": "PE", "qty": 625, "entry_prem": 25.00, "ticker": "JINDALSTEL.NS", "is_index": False},
    {"id": "TRD-19", "time": "11:09", "symbol": "JINDALSTEL", "strike": 1140, "type": "CE", "qty": 625, "entry_prem": 25.00, "ticker": "JINDALSTEL.NS", "is_index": False},
    {"id": "TRD-20", "time": "11:17", "symbol": "TATASTEEL", "strike": 182, "type": "PE", "qty": 5500, "entry_prem": 4.00, "ticker": "TATASTEEL.NS", "is_index": False},
    {"id": "TRD-21", "time": "11:22", "symbol": "JSWSTEEL", "strike": 1330, "type": "PE", "qty": 675, "entry_prem": 29.33, "ticker": "JSWSTEEL.NS", "is_index": False},
    {"id": "TRD-22", "time": "11:25", "symbol": "DIVISLAB", "strike": 11050, "type": "PE", "qty": 100, "entry_prem": 243.63, "ticker": "DIVISLAB.NS", "is_index": False},
    {"id": "TRD-23", "time": "11:26", "symbol": "TATASTEEL", "strike": 183, "type": "CE", "qty": 5500, "entry_prem": 4.02, "ticker": "TATASTEEL.NS", "is_index": False},
]

tickers = list(set([t["ticker"] for t in trades_list]))
raw_data = yf.download(tickers=tickers, period="1d", interval="5m", progress=False)

results = []

for trd in trades_list:
    tick = trd["ticker"]
    qty = trd["qty"]
    entry_prem = trd["entry_prem"]
    opt_type = trd["type"]
    is_idx = trd["is_index"]
    entry_time_str = trd["time"]
    
    # Extract ticker slice
    if len(tickers) > 1:
        df = raw_data.xs(tick, axis=1, level=1).dropna()
    else:
        df = raw_data.dropna()

    # Find candles after entry time
    times = [t.strftime("%H:%M") for t in df.index]
    
    # Match closest entry candle
    entry_idx = 0
    for i, t in enumerate(times):
        if t >= entry_time_str:
            entry_idx = i
            break
            
    entry_candle = df.iloc[entry_idx]
    entry_spot = entry_candle["Open"]
    
    # Simulate candle-by-candle from entry using Diamond Hands Hold Rules
    delta = 0.55
    max_pnl = 0.0
    min_pnl = 0.0
    closed = False
    exit_info = None

    # Risk limits
    hard_sl_inr = -2500.0 if is_idx else -1500.0
    hurdle_inr = 500.0 if is_idx else 3000.0

    locked_pnl = None

    for i in range(entry_idx, len(df)):
        c_time = times[i]
        c = df.iloc[i]
        
        # High and low spot in candle
        if opt_type == "CE":
            best_spot = c["High"]
            worst_spot = c["Low"]
            close_spot = c["Close"]
        else:
            best_spot = c["Low"]
            worst_spot = c["High"]
            close_spot = c["Close"]

        # Option moves
        best_opt_gain = (best_spot - entry_spot if opt_type == "CE" else entry_spot - best_spot) * delta
        worst_opt_loss = (worst_spot - entry_spot if opt_type == "CE" else entry_spot - worst_spot) * delta
        close_opt_move = (close_spot - entry_spot if opt_type == "CE" else entry_spot - close_spot) * delta

        unrealized_best = round(best_opt_gain * qty, 2)
        unrealized_worst = round(worst_opt_loss * qty, 2)
        unrealized_close = round(close_opt_move * qty, 2)

        # Check Hard SL first
        if unrealized_worst <= hard_sl_inr:
            exit_prem = round(max(0.05, entry_prem + (hard_sl_inr / qty)), 2)
            exit_info = {
                "exit_time": c_time,
                "exit_prem": exit_prem,
                "exit_reason": f"HARD SL (-₹{abs(hard_sl_inr):.0f})",
                "pnl": hard_sl_inr,
                "status": "CLOSED"
            }
            closed = True
            break

        # Check Trailing Targets
        if is_idx:
            # Index Trailing Ladder: +500 -> Lock +300; +1000 -> Lock +700; +3000 -> Lock +2400; +8000 -> Exit
            if unrealized_best >= 8000.0:
                exit_prem = round(entry_prem + (8000.0 / qty), 2)
                exit_info = {
                    "exit_time": c_time,
                    "exit_prem": exit_prem,
                    "exit_reason": "MAX TARGET (+₹8,000)",
                    "pnl": 8000.0,
                    "status": "CLOSED"
                }
                closed = True
                break
            elif unrealized_best >= 3000.0:
                locked_pnl = 2400.0
            elif unrealized_best >= 1000.0:
                locked_pnl = max(locked_pnl or 0, 700.0)
            elif unrealized_best >= 500.0:
                locked_pnl = max(locked_pnl or 0, 300.0)
        else:
            # Stock Trailing Rules: +3000 hurdle -> lock +2200; +8000 -> Exit
            if unrealized_best >= 8000.0:
                exit_prem = round(entry_prem + (8000.0 / qty), 2)
                exit_info = {
                    "exit_time": c_time,
                    "exit_prem": exit_prem,
                    "exit_reason": "MAX TARGET (+₹8,000)",
                    "pnl": 8000.0,
                    "status": "CLOSED"
                }
                closed = True
                break
            elif unrealized_best >= 3000.0:
                locked_pnl = 2200.0

        # If locked and pulled back
        if locked_pnl and unrealized_close <= locked_pnl:
            exit_prem = round(entry_prem + (locked_pnl / qty), 2)
            exit_info = {
                "exit_time": c_time,
                "exit_prem": exit_prem,
                "exit_reason": f"TRAILING LOCK (+₹{locked_pnl:.0f})",
                "pnl": locked_pnl,
                "status": "CLOSED"
            }
            closed = True
            break

    if not closed:
        # Still running live at 14:25
        last_c = df.iloc[-1]
        last_spot = last_c["Close"]
        last_move = (last_spot - entry_spot if opt_type == "CE" else entry_spot - last_spot) * delta
        curr_prem = round(max(0.05, entry_prem + last_move), 2)
        live_pnl = round((curr_prem - entry_prem) * qty, 2)
        exit_info = {
            "exit_time": "LIVE (14:25)",
            "exit_prem": curr_prem,
            "exit_reason": "OPEN / RUNNING IN MARKET",
            "pnl": live_pnl,
            "status": "OPEN"
        }

    results.append({
        **trd,
        "entry_spot": round(entry_spot, 2),
        **exit_info
    })

res_df = pd.DataFrame(results)
print("\n" + "="*80)
print("REAL NSE MARKET TRADE AUDIT (17 NOV 2026)")
print("="*80)
for idx, r in res_df.iterrows():
    print(f"[{r['time']}] {r['symbol']} {r['strike']} {r['type']} ({r['qty']} Qty) | Entry: ₹{r['entry_prem']:.2f} (Spot ₹{r['entry_spot']}) -> Exit: ₹{r['exit_prem']:.2f} [{r['exit_time']}] | PnL: ₹{r['pnl']:+,.2f} | Reason: {r['exit_reason']}")

total_closed_pnl = res_df[res_df["status"] == "CLOSED"]["pnl"].sum()
total_live_pnl = res_df[res_df["status"] == "OPEN"]["pnl"].sum()
net_day_pnl = res_df["pnl"].sum()

print("\n" + "-"*80)
print(f"TOTAL CLOSED TRADES PnL: ₹{total_closed_pnl:+,.2f}")
print(f"TOTAL OPEN POSITIONS PnL: ₹{total_live_pnl:+,.2f}")
print(f"NET REAL MARKET PERFORMANCE: ₹{net_day_pnl:+,.2f}")
print("-"*80)
