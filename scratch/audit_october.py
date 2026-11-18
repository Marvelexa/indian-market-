import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
import csv
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS

def run_october_audit():
    engine = IndianPastDateReplayEngine()
    oct_dates = [d for d in engine.sorted_dates if "-10-" in d]

    days_summary = []
    all_trades = []
    total_oct_pnl = 0.0
    total_trades = 0
    total_wins = 0

    for d in oct_dates:
        engine.set_date(d, auto_play=True)
        engine.is_running = True
        for _ in range(TOTAL_DAY_SECONDS // 5):
            engine.advance_seconds(5)
        
        st = engine.get_state()
        w = st['wallet']
        pnl = w['realizedPnlInr']
        total_oct_pnl += pnl
        total_trades += w['totalTrades']
        total_wins += w['wins']
        
        day_meta = next((item for item in engine.available_days if item['date'] == d), {})
        
        day_info = {
            'date': d,
            'weekday': day_meta.get('weekday', ''),
            'niftyOpen': day_meta.get('niftyOpen', 0),
            'niftyClose': day_meta.get('niftyClose', 0),
            'niftyChangePct': day_meta.get('niftyChangePct', 0),
            'category': day_meta.get('category', ''),
            'trades': w['totalTrades'],
            'wins': w['wins'],
            'losses': w['losses'],
            'winRatePct': w['winRatePct'],
            'netPnlInr': pnl,
            'returnPct': round(pnl / 100000.0 * 100.0, 2),
            'tp1_3_locks': w['profitLockHits'],
            'tp4_6_runners': w['tpHits'],
            'smartSlHits': w['smartSlHits'],
            'maxLossHits': w['maxLossCapHits']
        }
        days_summary.append(day_info)

        for t in engine.closed_ledger:
            all_trades.append({
                'date': d,
                'time': t['exitTimeFormatted'],
                'symbol': t['symbol'],
                'displayName': t['displayName'],
                'side': t['side'],
                'isOption': t.get('isOption', False),
                'optionType': t.get('optionType', ''),
                'strike': t.get('optionStrike', ''),
                'entryPrice': t['entryPrice'],
                'exitPrice': t['exitPrice'],
                'netPnlInr': t['netPnlInr'],
                'exitReason': t['exitReason'],
                'exitBadge': t['exitBadgeLabel']
            })

    win_rate = round(total_wins / max(1, total_trades) * 100, 1)

    print("=" * 80)
    print(f"  NEXUS BHARAT // OCTOBER 2026 COMPLETE AUDIT (20 TRADING DAYS)")
    print(f"  Strategy: 6-Tier Scalper Ladder (500->3000) + Smart SL Shield")
    print("=" * 80)
    print(f"  Total Trades:     {total_trades}")
    print(f"  Total Wins:       {total_wins} ({win_rate}%)")
    print(f"  Total Losses:     {total_trades - total_wins}")
    print(f"  Total Net PnL:    ₹{total_oct_pnl:,.2f}")
    print(f"  Monthly Return:   {total_oct_pnl/100000.0*100:+.2f}% on ₹1L Base Capital")
    print("-" * 80)
    print(f"{'Date':<12} {'Day':<4} {'Nifty Chg':<10} {'Trades':<8} {'Wins':<6} {'WR %':<8} {'Net PnL (₹)':<14} {'Category'}")
    print("-" * 80)
    for r in days_summary:
        sign = "+" if r['netPnlInr'] >= 0 else ""
        print(f"{r['date']:<12} {r['weekday'][:3]:<4} {r['niftyChangePct']:>+6.2f}%    {r['trades']:<8} {r['wins']:<6} {r['winRatePct']:>5.1f}%  {sign}₹{r['netPnlInr']:>10,.2f}   {r['category']}")
    print("=" * 80)

    # Save JSON
    with open('october_2026_audit_summary.json', 'w') as f:
        json.dump({
            'meta': {
                'month': 'October 2026',
                'tradingDays': len(days_summary),
                'totalTrades': total_trades,
                'totalWins': total_wins,
                'winRatePct': win_rate,
                'totalNetPnlInr': total_oct_pnl,
                'monthlyReturnPct': round(total_oct_pnl / 100000.0 * 100.0, 2)
            },
            'dailyPerformance': days_summary,
            'allTrades': all_trades
        }, f, indent=2)

    # Save CSV for user
    with open('october_2026_daily_pnl.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'date', 'weekday', 'niftyOpen', 'niftyClose', 'niftyChangePct', 
            'category', 'trades', 'wins', 'losses', 'winRatePct', 
            'netPnlInr', 'returnPct', 'tp1_3_locks', 'tp4_6_runners', 
            'smartSlHits', 'maxLossHits'
        ])
        writer.writeheader()
        writer.writerows(days_summary)

    with open('october_2026_all_trades.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'date', 'time', 'symbol', 'displayName', 'side', 'isOption', 
            'optionType', 'strike', 'entryPrice', 'exitPrice', 
            'netPnlInr', 'exitReason', 'exitBadge'
        ])
        writer.writeheader()
        writer.writerows(all_trades)

    print("\nFiles generated:")
    print("  1. october_2026_audit_summary.json")
    print("  2. october_2026_daily_pnl.csv")
    print("  3. october_2026_all_trades.csv")

if __name__ == '__main__':
    run_october_audit()
