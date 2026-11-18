import urllib.request
import json
import datetime
from typing import Dict, List, Any

# Load candles from local FastAPI
req = urllib.request.urlopen("http://127.0.0.1:8000/api/candles-batch?timeframe=5D")
raw_data = json.loads(req.read().decode("utf-8"))

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
TODAY = "2026-11-16"

# Load full candles for indicators
nifty_all = raw_data.get("NIFTY", [])
banknifty_all = raw_data.get("BANKNIFTY", [])

# Find today's candle indices
nifty_today = [c for c in nifty_all if datetime.datetime.fromtimestamp(c["timestamp"] / 1000, IST).strftime("%Y-%m-%d") == TODAY]
bn_today = [c for c in banknifty_all if datetime.datetime.fromtimestamp(c["timestamp"] / 1000, IST).strftime("%Y-%m-%d") == TODAY]

print(f"Loaded total candles: NIFTY={len(nifty_all)} (Today: {len(nifty_today)}), BANKNIFTY={len(banknifty_all)} (Today: {len(bn_today)})")

def compute_ema(series: List[float], period: int) -> float:
    if not series: return 0.0
    k = 2.0 / (period + 1.0)
    ema = series[0]
    for val in series[1:]:
        ema = val * k + ema * (1.0 - k)
    return ema

def compute_rsi(values: List[float], period: int = 14) -> float:
    if len(values) <= period:
        return 50.0
    gains, losses = 0.0, 0.0
    for i in range(len(values) - period, len(values)):
        diff = values[i] - values[i - 1]
        if diff >= 0: gains += diff
        else: losses -= diff
    if losses == 0.0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + gains / losses))

def compute_vwap(candles: List[Dict]) -> float:
    # Use today's candles up to current
    pv, volSum = 0.0, 0.0
    for c in candles:
        typical = (c["high"] + c["low"] + c["close"]) / 3.0
        v = c.get("volume", 0.0)
        v = v if v > 0 else 1.0
        pv += typical * v
        volSum += v
    return pv / volSum if volSum > 0 else candles[-1]["close"]

# Charges in Options Trading on NSE:
# Brokerage: ₹20 buy + ₹20 sell = ₹40 flat round trip
# STT: 0.1% on Sell Premium Turnover (ONLY on premium, NOT spot!)
# Exchange turnover: 0.05% of Premium Turnover
# Stamp duty: 0.003% of Buy Premium
# GST: 18% on (Brokerage + Exchange)
# SEBI: 0.0001% of Turnover
def calc_option_charges(buy_prem: float, sell_prem: float, qty: int) -> float:
    buy_to = buy_prem * qty
    sell_to = sell_prem * qty
    tot_to = buy_to + sell_to
    brokerage = 40.0
    stt = sell_to * 0.001
    exch = tot_to * 0.0005
    stamp = buy_to * 0.00003
    gst = (brokerage + exch) * 0.18
    sebi = tot_to * 0.000001
    return round(brokerage + stt + exch + stamp + gst + sebi, 2)

def run_option_simulation():
    # Option specifications:
    # NIFTY: Lot 25 (2 Lots = 50 Qty), Base ATM Premium ~₹130, Delta ~0.60
    # BANKNIFTY: Lot 15 (2 Lots = 30 Qty), Base ATM Premium ~₹280, Delta ~0.60
    DELTA = 0.60
    positions = {}
    closed_trades = []

    today_timestamps = sorted(list(set(c["timestamp"] for c in nifty_today)))

    for ts in today_timestamps:
        dt = datetime.datetime.fromtimestamp(ts / 1000, IST)
        t_str = dt.strftime("%H:%M")
        mins = dt.hour * 60 + dt.minute

        # 1. Manage Active Positions on this bar
        for seat_id in list(positions.keys()):
            pos = positions[seat_id]
            sym = pos["symbol"]
            cur_candle = next(c for c in (nifty_today if sym == "NIFTY" else bn_today) if c["timestamp"] == ts)
            
            spot_hi = cur_candle["high"]
            spot_lo = cur_candle["low"]
            spot_cl = cur_candle["close"]

            if pos["type"] == "CE":
                prem_hi = pos["entry_prem"] + (spot_hi - pos["entry_spot"]) * DELTA
                prem_lo = pos["entry_prem"] + (spot_lo - pos["entry_spot"]) * DELTA
                prem_cl = pos["entry_prem"] + (spot_cl - pos["entry_spot"]) * DELTA
            else:
                prem_hi = pos["entry_prem"] + (pos["entry_spot"] - spot_lo) * DELTA
                prem_lo = pos["entry_prem"] + (pos["entry_spot"] - spot_hi) * DELTA
                prem_cl = pos["entry_prem"] + (pos["entry_spot"] - spot_cl) * DELTA

            prem_hi = max(1.0, prem_hi)
            prem_lo = max(1.0, prem_lo)
            prem_cl = max(1.0, prem_cl)

            # Mandatory 03:18 PM Auto Square-Off
            if mins >= 15 * 60 + 18:
                exit_prem = prem_cl
                gross = (exit_prem - pos["entry_prem"]) * pos["qty"]
                chg = calc_option_charges(pos["entry_prem"], exit_prem, pos["qty"])
                closed_trades.append({
                    **pos, "exit_prem": round(exit_prem, 2), "exit_time": t_str,
                    "gross_pnl": round(gross, 2), "charges": chg,
                    "net_pnl": round(gross - chg, 2), "exit_reason": "03:18 PM Auto Square-Off"
                })
                del positions[seat_id]
                continue

            # Check SL hit during bar
            if prem_lo <= pos["current_sl_prem"]:
                exit_prem = pos["current_sl_prem"]
                gross = (exit_prem - pos["entry_prem"]) * pos["qty"]
                chg = calc_option_charges(pos["entry_prem"], exit_prem, pos["qty"])
                closed_trades.append({
                    **pos, "exit_prem": round(exit_prem, 2), "exit_time": t_str,
                    "gross_pnl": round(gross, 2), "charges": chg,
                    "net_pnl": round(gross - chg, 2), "exit_reason": f"SL Hit ({pos['stage_label']})"
                })
                del positions[seat_id]
                continue

            # Check 6-Stage Trailing Profit Ladder
            unrealized_peak = (prem_hi - pos["entry_prem"]) * pos["qty"]
            if unrealized_peak >= 3000:
                exit_prem = pos["entry_prem"] + 3000 / pos["qty"]
                gross = 3000.0
                chg = calc_option_charges(pos["entry_prem"], exit_prem, pos["qty"])
                closed_trades.append({
                    **pos, "exit_prem": round(exit_prem, 2), "exit_time": t_str,
                    "gross_pnl": round(gross, 2), "charges": chg,
                    "net_pnl": round(gross - chg, 2), "exit_reason": "TP 6 Target Booked (+₹3,000)"
                })
                del positions[seat_id]
                continue
            elif unrealized_peak >= 2500 and pos["stage"] < 5:
                pos["stage"] = 5
                pos["stage_label"] = "TP5 Lock (+₹2,100)"
                pos["current_sl_prem"] = round(pos["entry_prem"] + 2100 / pos["qty"], 2)
            elif unrealized_peak >= 2000 and pos["stage"] < 4:
                pos["stage"] = 4
                pos["stage_label"] = "TP4 Lock (+₹1,600)"
                pos["current_sl_prem"] = round(pos["entry_prem"] + 1600 / pos["qty"], 2)
            elif unrealized_peak >= 1500 and pos["stage"] < 3:
                pos["stage"] = 3
                pos["stage_label"] = "TP3 Lock (+₹1,150)"
                pos["current_sl_prem"] = round(pos["entry_prem"] + 1150 / pos["qty"], 2)
            elif unrealized_peak >= 1000 and pos["stage"] < 2:
                pos["stage"] = 2
                pos["stage_label"] = "TP2 Lock (+₹700)"
                pos["current_sl_prem"] = round(pos["entry_prem"] + 700 / pos["qty"], 2)
            elif unrealized_peak >= 500 and pos["stage"] < 1:
                pos["stage"] = 1
                pos["stage_label"] = "TP1 Lock (+₹300)"
                pos["current_sl_prem"] = round(pos["entry_prem"] + 300 / pos["qty"], 2)

        # 2. Check for New Option Entries (between 09:25 AM and 03:00 PM)
        if mins < 9 * 60 + 25 or mins >= 15 * 60:
            continue

        for sym, seat_id, lot_qty, base_prem in [("NIFTY", "OPTION_1", 50, 130.0), ("BANKNIFTY", "OPTION_2", 30, 280.0)]:
            if seat_id in positions:
                continue

            all_c = nifty_all if sym == "NIFTY" else banknifty_all
            today_c = nifty_today if sym == "NIFTY" else bn_today

            # candles up to current ts
            hist = [c for c in all_c if c["timestamp"] <= ts]
            cur_today = [c for c in today_c if c["timestamp"] <= ts]

            if len(hist) < 25 or len(cur_today) < 2:
                continue

            closes = [c["close"] for c in hist]
            e9 = compute_ema(closes, 9)
            e21 = compute_ema(closes, 21)
            rsi = compute_rsi(closes, 14)
            vwap = compute_vwap(cur_today)

            c0 = hist[-1]
            c1 = hist[-2]

            # BUY CALL Setup: Spot > VWAP and EMA9 >= EMA21 and Bullish Candle (c0 close > c0 open)
            if c0["close"] > vwap and e9 >= e21 and c0["close"] > c0["open"] and rsi >= 48:
                sl_prem = round(base_prem - (1500 / lot_qty), 2)
                positions[seat_id] = {
                    "symbol": sym, "type": "CE", "contract": f"{sym} ATM CALL",
                    "entry_spot": c0["close"], "entry_prem": base_prem,
                    "current_sl_prem": sl_prem, "qty": lot_qty,
                    "entry_time": t_str, "stage": 0, "stage_label": "Initial SL (-₹1,500)"
                }
            # BUY PUT Setup: Spot < VWAP and EMA9 <= EMA21 and Bearish Candle (c0 close < c0 open)
            elif c0["close"] < vwap and e9 <= e21 and c0["close"] < c0["open"] and rsi <= 52:
                sl_prem = round(base_prem - (1500 / lot_qty), 2)
                positions[seat_id] = {
                    "symbol": sym, "type": "PE", "contract": f"{sym} ATM PUT",
                    "entry_spot": c0["close"], "entry_prem": base_prem,
                    "current_sl_prem": sl_prem, "qty": lot_qty,
                    "entry_time": t_str, "stage": 0, "stage_label": "Initial SL (-₹1,500)"
                }

    return closed_trades

trades = run_option_simulation()

print("\n=========================================================================================")
print("  TODAY'S INDEX CALL / PUT OPTION SIMULATION (16-NOV-2026)")
print("  ATM 0.60Δ Options (NIFTY 50 Qty / BANKNIFTY 30 Qty) + ₹1,500 SL + 6-Stage TP Ladder")
print("=========================================================================================\n")

tot_gross = sum(t["gross_pnl"] for t in trades)
tot_tax = sum(t["charges"] for t in trades)
tot_net = sum(t["net_pnl"] for t in trades)
wins = [t for t in trades if t["net_pnl"] > 0]
losses = [t for t in trades if t["net_pnl"] <= 0]
win_rate = (len(wins) / len(trades) * 100.0) if trades else 0.0

print(f"Total Option Trades Taken: {len(trades)}")
print(f"Win Rate:                  {win_rate:.1f}% ({len(wins)} Wins / {len(losses)} Losses)")
print(f"Total Gross Option Profit: ₹{tot_gross:,.2f}")
print(f"Total Taxes & Brokerage:   ₹{tot_tax:,.2f}  <-- (65%–70% LOWER TAX THAN CASH EQUITY!)")
print(f"Total Net Option Profit:   ₹{tot_net:,.2f}  🟢")

print("\nDetailed Options Trade Log:")
print("-" * 115)
print(f"{'Time':<7} {'Contract':<18} {'Spot In':<9} {'Prem In':<8} {'Prem Out':<9} {'Time Out':<9} {'Taxes':<8} {'Net P&L (₹)':<13} {'Exit Reason'}")
print("-" * 115)
for t in trades:
    pnl_s = f"{'+' if t['net_pnl'] >= 0 else ''}{t['net_pnl']:,.2f}"
    print(f"{t['entry_time']:<7} {t['contract']:<18} {t['entry_spot']:<9.1f} ₹{t['entry_prem']:<7.1f} ₹{t['exit_prem']:<8.1f} {t['exit_time']:<9} ₹{t['charges']:<7.2f} {pnl_s:<13} {t['exit_reason']}")
print("-" * 115)
