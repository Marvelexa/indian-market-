import sys
sys.path.insert(0, r"d:\new start")
import json, datetime

from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS

# Let's write an exact simulation of today's options using the replay engine data
engine = IndianPastDateReplayEngine.get_instance()
day_bars = engine.by_date_5m.get("2026-11-16", {})

nifty_bars = day_bars.get("NIFTY", [])
bn_bars = day_bars.get("BANKNIFTY", [])
print(f"Loaded bars: NIFTY={len(nifty_bars)}, BANKNIFTY={len(bn_bars)}")

def run_pure_options_test():
    DELTA = 0.60
    positions = {}
    closed = []
    
    # 2 Lots: NIFTY 50 Qty, BANKNIFTY 30 Qty
    lots = {"NIFTY": 50, "BANKNIFTY": 30}
    base_prems = {"NIFTY": 130.0, "BANKNIFTY": 280.0}
    
    for i in range(1, len(nifty_bars)):
        n_c = nifty_bars[i]
        b_c = bn_bars[i]
        t_str = datetime.datetime.fromtimestamp(n_c["timestamp"]/1000, datetime.timezone(datetime.timedelta(hours=5, minutes=30))).strftime("%H:%M")
        
        # Check active positions
        for sym in list(positions.keys()):
            pos = positions[sym]
            cur_bar = n_c if sym == "NIFTY" else b_c
            hi, lo, cl = float(cur_bar["high"]), float(cur_bar["low"]), float(cur_bar["close"])
            
            if pos["type"] == "CE":
                prem_hi = pos["entry_prem"] + (hi - pos["entry_spot"]) * DELTA
                prem_lo = pos["entry_prem"] + (lo - pos["entry_spot"]) * DELTA
                prem_cl = pos["entry_prem"] + (cl - pos["entry_spot"]) * DELTA
            else:
                prem_hi = pos["entry_prem"] + (pos["entry_spot"] - lo) * DELTA
                prem_lo = pos["entry_prem"] + (pos["entry_spot"] - hi) * DELTA
                prem_cl = pos["entry_prem"] + (pos["entry_spot"] - cl) * DELTA
            
            # Trailing targets
            gain_peak = (prem_hi - pos["entry_prem"]) * pos["qty"]
            
            # Check TP6 (+₹3,000)
            if gain_peak >= 3000.0:
                closed.append({**pos, "exit_time": t_str, "exit_prem": pos["entry_prem"] + 3000.0/pos["qty"], "net_pnl": 3000.0 - 65.0, "reason": "TP 6 Target Booked (+₹3,000)"})
                del positions[sym]
                continue
            elif gain_peak >= 2500.0 and pos["stage"] < 5:
                pos["stage"] = 5
                pos["sl_prem"] = pos["entry_prem"] + 2100.0 / pos["qty"]
            elif gain_peak >= 2000.0 and pos["stage"] < 4:
                pos["stage"] = 4
                pos["sl_prem"] = pos["entry_prem"] + 1600.0 / pos["qty"]
            elif gain_peak >= 1500.0 and pos["stage"] < 3:
                pos["stage"] = 3
                pos["sl_prem"] = pos["entry_prem"] + 1150.0 / pos["qty"]
            elif gain_peak >= 1000.0 and pos["stage"] < 2:
                pos["stage"] = 2
                pos["sl_prem"] = pos["entry_prem"] + 700.0 / pos["qty"]
            elif gain_peak >= 500.0 and pos["stage"] < 1:
                pos["stage"] = 1
                pos["sl_prem"] = pos["entry_prem"] + 300.0 / pos["qty"]
            
            # Check SL
            if prem_lo <= pos["sl_prem"]:
                loss = (pos["sl_prem"] - pos["entry_prem"]) * pos["qty"]
                closed.append({**pos, "exit_time": t_str, "exit_prem": pos["sl_prem"], "net_pnl": round(loss - 65.0, 2), "reason": f"SL Hit (Stage {pos['stage']})"})
                del positions[sym]
                continue
        
        # Signal check (from 09:25 onward)
        # Nifty & BankNifty confluence
        if i >= 2 and i < len(nifty_bars) - 2:
            n_close = float(n_c["close"])
            n_open = float(n_c["open"])
            b_close = float(b_c["close"])
            b_open = float(b_c["open"])
            
            # Bullish confluence
            if n_close > n_open and b_close > b_open:
                for sym, bar, base_p in [("BANKNIFTY", b_c, 280.0), ("NIFTY", n_c, 130.0)]:
                    if sym not in positions:
                        qty = lots[sym]
                        positions[sym] = {
                            "symbol": sym, "type": "CE", "entry_spot": float(bar["close"]),
                            "entry_prem": base_p, "qty": qty, "sl_prem": round(base_p - 1500.0/qty, 2),
                            "entry_time": t_str, "stage": 0
                        }
    
    return closed

trades = run_pure_options_test()
print(f"\nTotal Option Trades: {len(trades)}")
net = sum(t['net_pnl'] for t in trades)
print(f"Total Net PnL: ₹{net:,.2f}")
for t in trades:
    print(f"{t['entry_time']} -> {t['exit_time']} | {t['symbol']} {t['type']} | PnL: ₹{t['net_pnl']:<10.2f} | {t['reason']}")
