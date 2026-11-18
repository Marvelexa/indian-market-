import json

with open('october_2026_audit_summary.json') as f:
    d = json.load(f)

days = d['dailyPerformance']
print(f"Total Trading Days in October: {len(days)}")
print("-" * 85)
win_days = [day for day in days if day['netPnlInr'] > 0]
loss_days = [day for day in days if day['netPnlInr'] <= 0]

print(f"Winning Days ({len(win_days)} days):")
for day in win_days:
    print(f"  {day['date']} | {day['weekday'][:3]} | Net: +INR {day['netPnlInr']:>8,.2f} | Trades: {day['trades']:>2} (W:{day['wins']:>2}, L:{day['losses']:>2}) | WR: {day['winRatePct']:>5.1f}% | {day['category']}")

print("\nLosing Days ({len(loss_days)} days):")
for day in loss_days:
    print(f"  {day['date']} | {day['weekday'][:3]} | Net:  INR {day['netPnlInr']:>8,.2f} | Trades: {day['trades']:>2} (W:{day['wins']:>2}, L:{day['losses']:>2}) | WR: {day['winRatePct']:>5.1f}% | {day['category']}")

tot_win_pnl = sum(d['netPnlInr'] for d in win_days)
tot_loss_pnl = sum(d['netPnlInr'] for d in loss_days)
print("-" * 85)
print(f"Gross Profit on Win Days:  +INR {tot_win_pnl:>9,.2f}")
print(f"Gross Loss on Loss Days:   -INR {abs(tot_loss_pnl):>9,.2f}")
print(f"Net Profit (1-lot base):   +INR {tot_win_pnl + tot_loss_pnl:>9,.2f}")
