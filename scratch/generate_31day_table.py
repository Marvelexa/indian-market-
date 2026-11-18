import json
import datetime

with open('october_2026_audit_summary.json') as f:
    data = json.load(f)

meta = data['meta']
trading_days_map = {d['date']: d for d in data['dailyPerformance']}

start_date = datetime.date(2026, 10, 1)
end_date = datetime.date(2026, 10, 31)

balance = 100000.0
cumulative_pnl = 0.0

print("| Date | Day | Market / Regime | Trades | W / L | Win Rate | Daily P&L (₹) | Running Balance (₹) | Status |")
print("| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |")

cur = start_date
while cur <= end_date:
    d_str = cur.strftime("%Y-%m-%d")
    weekday = cur.strftime("%A")
    short_date = cur.strftime("%d %b %Y")
    
    if d_str in trading_days_map:
        d = trading_days_map[d_str]
        pnl = d['netPnlInr']
        balance += pnl
        cumulative_pnl += pnl
        pnl_str = f"+₹{pnl:,.2f}" if pnl >= 0 else f"-₹{abs(pnl):,.2f}"
        wr_str = f"{d['winRatePct']:.1f}%"
        trades_str = str(d['trades'])
        wl_str = f"{d['wins']}W / {d['losses']}L"
        status = "🟢 PROFIT" if pnl > 0 else "🔴 LOSS"
        category = d['category']
        print(f"| {short_date} | {weekday[:3]} | {category} | {trades_str} | {wl_str} | {wr_str} | **{pnl_str}** | ₹{balance:,.2f} | {status} |")
    else:
        # Weekend or Holiday
        if weekday in ["Saturday", "Sunday"]:
            note = "Weekend (NSE Closed)"
        elif d_str == "2026-10-02":
            note = "Gandhi Jayanti (NSE Holiday)"
        elif d_str == "2026-10-20":
            note = "Dussehra / Holiday"
        else:
            note = "NSE Holiday"
        print(f"| {short_date} | {weekday[:3]} | *{note}* | — | — | — | ₹0.00 | ₹{balance:,.2f} | ⚪ CLOSED |")
    
    cur += datetime.timedelta(days=1)

print("\n--- SUMMARY METRICS ---")
print(f"Total Trading Days: {meta['tradingDays']}")
print(f"Total Trades: {meta['totalTrades']}")
print(f"Total Wins: {meta['totalWins']} ({meta['winRatePct']}%)")
print(f"Total Losses: {meta['totalTrades'] - meta['totalWins']}")
print(f"Net Realized PnL: INR {meta['totalNetPnlInr']:,.2f}")
print(f"Monthly Return on 1 Lakh: {meta['monthlyReturnPct']:+.2f}%")
print(f"ROE on Deployed Margin (25k): {meta['totalNetPnlInr']/25000.0*100:+.2f}%")
print(f"Final Account Balance: INR {balance:,.2f}")
