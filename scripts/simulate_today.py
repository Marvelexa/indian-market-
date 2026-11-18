import urllib.request
import json
import datetime
from typing import Dict, List, Any

req = urllib.request.urlopen("http://127.0.0.1:8000/api/candles-batch?timeframe=5D")
raw_data = json.loads(req.read().decode("utf-8"))

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
TODAY = "2026-11-16"

WHITELIST = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "BHARTIARTL",
    "SBIN", "INFY", "LICI", "ITC", "HINDUNILVR", "LT",
    "BAJFINANCE", "M&M", "SUNPHARMA"
]

today_candles = {}
for sym in WHITELIST + ["NIFTY", "BANKNIFTY"]:
    c_list = raw_data.get(sym, [])
    parsed = []
    for c in c_list:
        dt = datetime.datetime.fromtimestamp(c["timestamp"] / 1000, IST)
        c["dt"] = dt
        c["date_str"] = dt.strftime("%Y-%m-%d")
        c["time_str"] = dt.strftime("%H:%M")
        parsed.append(c)
    parsed.sort(key=lambda x: x["timestamp"])
    today_candles[sym] = parsed

timestamps = sorted(list(set(
    c["timestamp"] for sym in WHITELIST for c in today_candles[sym] if c["date_str"] == TODAY
)))

def compute_ema(series: List[float], period: int) -> float:
    if len(series) < period:
        return series[-1] if series else 0.0
    k = 2.0 / (period + 1.0)
    ema = sum(series[:period]) / period
    for val in series[period:]:
        ema = val * k + ema * (1.0 - k)
    return ema

def compute_rsi(closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    if len(gains) < period:
        return 50.0
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def compute_vwap(candles_today: List[Dict]) -> float:
    pv = sum(c["close"] * c.get("volume", 1) for c in candles_today)
    v = sum(c.get("volume", 1) for c in candles_today)
    return pv / v if v > 0 else (candles_today[-1]["close"] if candles_today else 0.0)

SEATS = {
    "TREND_1": None, "TREND_2": None,
    "CHOP_1": None, "CHOP_2": None,
    "OPTION_1": None, "OPTION_2": None
}

closed_trades = []

for t_idx, ts in enumerate(timestamps):
    dt = datetime.datetime.fromtimestamp(ts / 1000, IST)
    time_str = dt.strftime("%H:%M")
    mins_from_midnight = dt.hour * 60 + dt.minute

    # Update existing positions
    for seat_id, pos in list(SEATS.items()):
        if pos is None:
            continue
        sym = pos["symbol"]
        sym_candles = [c for c in today_candles[sym] if c["timestamp"] <= ts]
        if not sym_candles:
            continue
        curr_bar = sym_candles[-1]
        hi, lo, cl = curr_bar["high"], curr_bar["low"], curr_bar["close"]
        mult = pos.get("delta_multiplier", 1.0) * pos["qty"]

        # 03:18 PM Auto Square-Off
        if mins_from_midnight >= 15 * 60 + 18:
            exit_price = cl
            gross_pnl = (exit_price - pos["entry"]) * mult if pos["side"] == "BUY" else (pos["entry"] - exit_price) * mult
            pos["exit_price"] = exit_price
            pos["exit_time"] = time_str
            pos["exit_reason"] = "03:18 PM Auto Square-Off"
            pos["gross_pnl"] = gross_pnl
            pos["charges"] = round(exit_price * pos["qty"] * 0.00045 + 20, 2)
            pos["net_pnl"] = round(gross_pnl - pos["charges"], 2)
            closed_trades.append(pos)
            SEATS[seat_id] = None
            continue

        if pos["side"] == "BUY":
            if lo <= pos["sl"]:
                exit_price = pos["sl"]
                gross_pnl = (exit_price - pos["entry"]) * mult
                pos["exit_price"] = exit_price
                pos["exit_time"] = time_str
                pos["exit_reason"] = f"SL Hit ({pos['stage_note']})"
                pos["gross_pnl"] = gross_pnl
                pos["charges"] = round(exit_price * pos["qty"] * 0.00045 + 20, 2)
                pos["net_pnl"] = round(gross_pnl - pos["charges"], 2)
                closed_trades.append(pos)
                SEATS[seat_id] = None
                continue

            unrealized_high_pnl = (hi - pos["entry"]) * mult
            if unrealized_high_pnl >= 3000:
                exit_price = pos["entry"] + 3000 / mult
                gross_pnl = 3000.0
                pos["exit_price"] = round(exit_price, 2)
                pos["exit_time"] = time_str
                pos["exit_reason"] = "TP 6 Target Booked (+₹3,000)"
                pos["gross_pnl"] = gross_pnl
                pos["charges"] = round(exit_price * pos["qty"] * 0.00045 + 20, 2)
                pos["net_pnl"] = round(gross_pnl - pos["charges"], 2)
                closed_trades.append(pos)
                SEATS[seat_id] = None
                continue
            elif unrealized_high_pnl >= 2500 and pos["ladder_stage"] < 5:
                pos["ladder_stage"] = 5
                pos["sl"] = round(pos["entry"] + 2100 / mult, 2)
                pos["stage_note"] = "TP5 Hit (Locked +₹2,100)"
            elif unrealized_high_pnl >= 2000 and pos["ladder_stage"] < 4:
                pos["ladder_stage"] = 4
                pos["sl"] = round(pos["entry"] + 1600 / mult, 2)
                pos["stage_note"] = "TP4 Hit (Locked +₹1,600)"
            elif unrealized_high_pnl >= 1500 and pos["ladder_stage"] < 3:
                pos["ladder_stage"] = 3
                pos["sl"] = round(pos["entry"] + 1150 / mult, 2)
                pos["stage_note"] = "TP3 Hit (Locked +₹1,150)"
            elif unrealized_high_pnl >= 1000 and pos["ladder_stage"] < 2:
                pos["ladder_stage"] = 2
                pos["sl"] = round(pos["entry"] + 700 / mult, 2)
                pos["stage_note"] = "TP2 Hit (Locked +₹700)"
            elif unrealized_high_pnl >= 500 and pos["ladder_stage"] < 1:
                pos["ladder_stage"] = 1
                pos["sl"] = round(pos["entry"] + 300 / mult, 2)
                pos["stage_note"] = "TP1 Hit (Locked +₹300)"

        else: # SELL
            if hi >= pos["sl"]:
                exit_price = pos["sl"]
                gross_pnl = (pos["entry"] - exit_price) * mult
                pos["exit_price"] = exit_price
                pos["exit_time"] = time_str
                pos["exit_reason"] = f"SL Hit ({pos['stage_note']})"
                pos["gross_pnl"] = gross_pnl
                pos["charges"] = round(exit_price * pos["qty"] * 0.00045 + 20, 2)
                pos["net_pnl"] = round(gross_pnl - pos["charges"], 2)
                closed_trades.append(pos)
                SEATS[seat_id] = None
                continue

            unrealized_high_pnl = (pos["entry"] - lo) * mult
            if unrealized_high_pnl >= 3000:
                exit_price = pos["entry"] - 3000 / mult
                gross_pnl = 3000.0
                pos["exit_price"] = round(exit_price, 2)
                pos["exit_time"] = time_str
                pos["exit_reason"] = "TP 6 Target Booked (+₹3,000)"
                pos["gross_pnl"] = gross_pnl
                pos["charges"] = round(exit_price * pos["qty"] * 0.00045 + 20, 2)
                pos["net_pnl"] = round(gross_pnl - pos["charges"], 2)
                closed_trades.append(pos)
                SEATS[seat_id] = None
                continue
            elif unrealized_high_pnl >= 2500 and pos["ladder_stage"] < 5:
                pos["ladder_stage"] = 5
                pos["sl"] = round(pos["entry"] - 2100 / mult, 2)
                pos["stage_note"] = "TP5 Hit (Locked +₹2,100)"
            elif unrealized_high_pnl >= 2000 and pos["ladder_stage"] < 4:
                pos["ladder_stage"] = 4
                pos["sl"] = round(pos["entry"] - 1600 / mult, 2)
                pos["stage_note"] = "TP4 Hit (Locked +₹1,600)"
            elif unrealized_high_pnl >= 1500 and pos["ladder_stage"] < 3:
                pos["ladder_stage"] = 3
                pos["sl"] = round(pos["entry"] - 1150 / mult, 2)
                pos["stage_note"] = "TP3 Hit (Locked +₹1,150)"
            elif unrealized_high_pnl >= 1000 and pos["ladder_stage"] < 2:
                pos["ladder_stage"] = 2
                pos["sl"] = round(pos["entry"] - 700 / mult, 2)
                pos["stage_note"] = "TP2 Hit (Locked +₹700)"
            elif unrealized_high_pnl >= 500 and pos["ladder_stage"] < 1:
                pos["ladder_stage"] = 1
                pos["sl"] = round(pos["entry"] - 300 / mult, 2)
                pos["stage_note"] = "TP1 Hit (Locked +₹300)"

    if mins_from_midnight < 9 * 60 + 25 or mins_from_midnight >= 15 * 60 + 5:
        continue

    # Market Breadth
    bull_count, bear_count = 0, 0
    for sym in WHITELIST:
        history = [c for c in today_candles[sym] if c["timestamp"] <= ts]
        if len(history) < 20: continue
        today_sub = [c for c in history if c["date_str"] == TODAY]
        vw = compute_vwap(today_sub)
        closes = [c["close"] for c in history]
        e9 = compute_ema(closes, 9)
        e21 = compute_ema(closes, 21)
        cl = closes[-1]
        if cl > vw and e9 > e21: bull_count += 1
        elif cl < vw and e9 < e21: bear_count += 1

    breadth_pct = (bull_count / len(WHITELIST)) * 100.0
    dominant_bias = "BULLISH" if breadth_pct >= 55.0 else ("BEARISH" if (bear_count / len(WHITELIST)) * 100.0 >= 55.0 else "SECTOR_ROTATION")

    # Index Option Signals
    for opt_seat, idx_sym, lot_sz in [("OPTION_1", "NIFTY", 25), ("OPTION_2", "BANKNIFTY", 15)]:
        if SEATS[opt_seat] is not None:
            continue
        idx_history = [c for c in today_candles[idx_sym] if c["timestamp"] <= ts]
        if len(idx_history) < 30: continue
        idx_today = [c for c in idx_history if c["date_str"] == TODAY]
        if len(idx_today) < 3: continue
        vw = compute_vwap(idx_today)
        closes = [c["close"] for c in idx_history]
        e9 = compute_ema(closes, 9)
        e21 = compute_ema(closes, 21)
        rsi = compute_rsi(closes, 14)
        c0, c1 = idx_history[-1], idx_history[-2]

        if c0["close"] > vw and e9 > e21 and c0["close"] > c1["high"] and rsi >= 50:
            sl_pts = max(c0["close"] * 0.003, 20.0 if idx_sym == "NIFTY" else 60.0)
            SEATS[opt_seat] = {
                "symbol": idx_sym, "side": "BUY", "entry": c0["close"], "sl": round(c0["close"] - sl_pts, 2),
                "qty": lot_sz, "delta_multiplier": 0.60, "entry_time": time_str,
                "ladder_stage": 0, "stage_note": "Initial SL (-₹1,500 Risk)", "seat_id": opt_seat
            }
        elif c0["close"] < vw and e9 < e21 and c0["close"] < c1["low"] and rsi <= 50:
            sl_pts = max(c0["close"] * 0.003, 20.0 if idx_sym == "NIFTY" else 60.0)
            SEATS[opt_seat] = {
                "symbol": idx_sym, "side": "SELL", "entry": c0["close"], "sl": round(c0["close"] + sl_pts, 2),
                "qty": lot_sz, "delta_multiplier": 0.60, "entry_time": time_str,
                "ladder_stage": 0, "stage_note": "Initial SL (-₹1,500 Risk)", "seat_id": opt_seat
            }

    # Available Equity Seats
    available_seats = [sid for sid in ["TREND_1", "TREND_2", "CHOP_1", "CHOP_2"] if SEATS[sid] is None]
    if not available_seats:
        continue

    candidates = []
    for sym in WHITELIST:
        if any(p and p["symbol"] == sym for p in SEATS.values()):
            continue
        history = [c for c in today_candles[sym] if c["timestamp"] <= ts]
        if len(history) < 30: continue
        today_sub = [c for c in history if c["date_str"] == TODAY]
        if len(today_sub) < 3: continue

        vw = compute_vwap(today_sub)
        closes = [c["close"] for c in history]
        e9 = compute_ema(closes, 9)
        e21 = compute_ema(closes, 21)
        rsi = compute_rsi(closes, 14)
        c0, c1, c2 = history[-1], history[-2], history[-3]

        allowed_side = None
        if dominant_bias == "BULLISH": allowed_side = "BUY"
        elif dominant_bias == "BEARISH": allowed_side = "SELL"
        else:
            if c0["close"] > vw and e9 > e21: allowed_side = "BUY"
            elif c0["close"] < vw and e9 < e21: allowed_side = "SELL"

        if not allowed_side: continue

        rng = max(c0["high"] - c0["low"], 0.05)
        body = abs(c0["close"] - c0["open"])
        upper_wick = (c0["high"] - max(c0["open"], c0["close"])) / rng
        lower_wick = (min(c0["open"], c0["close"]) - c0["low"]) / rng
        recent3_low = min(c0["low"], c1["low"], c2["low"])
        recent3_high = max(c0["high"], c1["high"], c2["high"])

        if allowed_side == "BUY":
            trend_ok = c0["close"] > vw and e9 > e21
            val_ok = recent3_low <= max(e9, e21, vw) * 1.0035
            pa_ok = (
                (c0["close"] > c0["open"] and lower_wick >= 0.35 and upper_wick <= 0.25) or
                (c0["close"] > c0["open"] and c0["close"] > c1["open"] and c1["close"] < c1["open"]) or
                (c0["close"] > c0["open"] and c0["close"] > c1["high"] and body / rng >= 0.45) or
                (c0["close"] > c0["open"] and upper_wick <= 0.35 and rsi >= 46 and rsi <= 74)
            )
            if trend_ok and val_ok and pa_ok and 46 <= rsi <= 74:
                sl_price = round(recent3_low * (1.0 - 0.0015), 2)
                sl_dist = max(c0["close"] - sl_price, c0["close"] * 0.0035)
                qty = max(1, int(1500 / sl_dist))
                candidates.append({
                    "symbol": sym, "side": "BUY", "entry": c0["close"], "sl": sl_price,
                    "qty": qty, "sl_dist": sl_dist, "time": time_str
                })

        else:
            trend_ok = c0["close"] < vw and e9 < e21
            val_ok = recent3_high >= min(e9, e21, vw) * 0.9965
            pa_ok = (
                (c0["close"] < c0["open"] and upper_wick >= 0.35 and lower_wick <= 0.25) or
                (c0["close"] < c0["open"] and c0["close"] < c1["open"] and c1["close"] > c1["open"]) or
                (c0["close"] < c0["open"] and c0["close"] < c1["low"] and body / rng >= 0.45) or
                (c0["close"] < c0["open"] and lower_wick <= 0.35 and rsi <= 54 and rsi >= 26)
            )
            if trend_ok and val_ok and pa_ok and 26 <= rsi <= 54:
                sl_price = round(recent3_high * (1.0 + 0.0015), 2)
                sl_dist = max(sl_price - c0["close"], c0["close"] * 0.0035)
                qty = max(1, int(1500 / sl_dist))
                candidates.append({
                    "symbol": sym, "side": "SELL", "entry": c0["close"], "sl": sl_price,
                    "qty": qty, "sl_dist": sl_dist, "time": time_str
                })

    for i in range(min(len(candidates), len(available_seats))):
        c = candidates[i]
        sid = available_seats[i]
        SEATS[sid] = {
            "symbol": c["symbol"], "side": c["side"], "entry": c["entry"], "sl": c["sl"],
            "qty": c["qty"], "delta_multiplier": 1.0, "entry_time": c["time"],
            "ladder_stage": 0, "stage_note": "Initial SL (-₹1,500 Risk)", "seat_id": sid
        }

total_gross = sum(t["gross_pnl"] for t in closed_trades)
total_charges = sum(t["charges"] for t in closed_trades)
total_net = sum(t["net_pnl"] for t in closed_trades)
wins = [t for t in closed_trades if t["net_pnl"] > 0]
losses = [t for t in closed_trades if t["net_pnl"] <= 0]
win_rate = (len(wins) / len(closed_trades) * 100.0) if closed_trades else 0.0

print("\n=========================================================================================")
print(f"  TODAY'S COMPLETE 2+2+2 RETROSPECTIVE SIMULATION (16-NOV-2026)")
print(f"  Includes: 14 Stocks + Nifty/BankNifty 0.60Δ Options + ₹1,500 Breathing SL + 6-Stage TP")
print("=========================================================================================\n")

print(f"Total Trades Taken:       {len(closed_trades)}")
print(f"Win Rate:                 {win_rate:.1f}% ({len(wins)} Wins / {len(losses)} Losses)")
print(f"Total Gross P&L:          ₹{total_gross:,.2f}")
print(f"Total Taxes & Brokerage:  ₹{total_charges:,.2f}")
print(f"Total Net P&L:            ₹{total_net:,.2f}")
print("\nIndividual Trade Execution Log:")
print("-" * 115)
print(f"{'Time':<7} {'Seat':<9} {'Symbol':<12} {'Side':<5} {'Qty':<5} {'Entry':<9} {'Exit':<9} {'Exit Time':<10} {'Net P&L (₹)':<13} {'Exit Reason'}")
print("-" * 115)
for t in closed_trades:
    pnl_str = f"{'+' if t['net_pnl'] >= 0 else ''}{t['net_pnl']:,.2f}"
    print(f"{t['entry_time']:<7} {t['seat_id']:<9} {t['symbol']:<12} {t['side']:<5} {t['qty']:<5} ₹{t['entry']:<8.2f} ₹{t['exit_price']:<8.2f} {t['exit_time']:<10} {pnl_str:<13} {t['exit_reason']}")
print("-" * 115)
