import urllib.request
import json
import datetime

mcx_data = json.loads(urllib.request.urlopen('http://127.0.0.1:8000/api/mcx/candles-batch').read())

crude = mcx_data['CRUDEOIL']
# Filter bars starting from 14:00 to 23:20
trade_bars = []
for c in crude:
    dt = datetime.datetime.fromtimestamp(c['timestamp']/1000)
    if dt.date() == datetime.date(2026, 11, 16) and (14 <= dt.hour < 23 or (dt.hour == 23 and dt.minute <= 20)):
        trade_bars.append((dt.strftime('%H:%M'), c['open'], c['high'], c['low'], c['close']))

entry_time, _, _, _, entry_spot = trade_bars[0]
print(f"CRUDEOIL PUT TRADE ENTRY: {entry_time} IST @ Spot ₹{entry_spot:.2f}")

entry_prem = 150.0
lot_size = 100
delta = 0.55
peak_pnl = 0
locked_pnl = 0
stage = 0

for t, o, h, l, cl in trade_bars:
    spot_gain = entry_spot - l
    prem_gain = spot_gain * delta
    pnl = prem_gain * lot_size
    if pnl > peak_pnl:
        peak_pnl = pnl
    
    # Ladder check
    if peak_pnl >= 500 and stage < 1:
        stage = 1
        locked_pnl = 150
    if peak_pnl >= 1000 and stage < 2:
        stage = 2
        locked_pnl = 600
    if peak_pnl >= 2000 and stage < 3:
        stage = 3
        locked_pnl = 1400
    if peak_pnl >= 4000 and stage < 4:
        stage = 4
        locked_pnl = 3000
    if peak_pnl >= 8000:
        stage = 5
        locked_pnl = max(6500, peak_pnl - 1000)

exit_time, _, _, _, exit_spot = trade_bars[-1]
final_spot_drop = entry_spot - exit_spot
final_prem = entry_prem + final_spot_drop * delta
final_gross = (final_prem - entry_prem) * lot_size
final_net = final_gross - 62.0

print(f"CRUDEOIL PUT TRADE EXIT (11:20 PM AUTO SQ OFF): {exit_time} IST @ Spot ₹{exit_spot:.2f}")
print(f"Total Spot Drop: {final_spot_drop:.2f} points")
print(f"Option Entry Premium: ₹{entry_prem:.2f} -> Exit Premium: ₹{final_prem:.2f}")
print(f"Peak Floating PnL: +₹{peak_pnl:.2f} (Stage {stage})")
print(f"Final Realized Net P&L: +₹{final_net:.2f}")
