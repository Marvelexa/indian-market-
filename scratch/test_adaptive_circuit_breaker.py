import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from scratch.test_imic_confluence import InterMarketConfluenceEngine
from backend.replay_engine import TOTAL_DAY_SECONDS

def test_loss_cap(cap_val):
    class CappedEngine(InterMarketConfluenceEngine):
        def evaluate_seat_signals(self):
            if self.realized_pnl_inr <= cap_val:
                return
            super().evaluate_seat_signals()

    eng = CappedEngine()
    monthly_stats = {}
    total_pnl = 0.0

    for d in eng.sorted_dates:
        m = d[:7]
        if m not in monthly_stats:
            monthly_stats[m] = {"days": 0, "trades": 0, "wins": 0, "losses": 0, "pnl": 0.0, "green": 0, "red": 0}
        eng.set_date(d, auto_play=True)
        for _ in range(TOTAL_DAY_SECONDS // 5):
            eng.advance_seconds(5)
        st = eng.get_state()
        w = st['wallet']
        p = round(w['realizedPnlInr'], 2)
        t = w['totalTrades']
        wn = w['wins']
        ls = t - wn
        monthly_stats[m]["days"] += 1
        monthly_stats[m]["trades"] += t
        monthly_stats[m]["wins"] += wn
        monthly_stats[m]["losses"] += ls
        monthly_stats[m]["pnl"] += p
        if p > 0: monthly_stats[m]["green"] += 1
        else: monthly_stats[m]["red"] += 1
        total_pnl += p

    print(f"\n==================== CIRCUIT BREAKER AT INR {cap_val:,.0f} ====================")
    for m, v in sorted(monthly_stats.items()):
        wr = round((v['wins'] / v['trades']) * 100, 1) if v['trades'] > 0 else 0
        pnl_str = f"+INR {v['pnl']:,.2f}" if v['pnl'] >= 0 else f"-INR {abs(v['pnl']):,.2f}"
        margin_roe = f"+{v['pnl'] / 25000.0 * 100:.1f}%" if v['pnl'] >= 0 else f"-{abs(v['pnl']) / 25000.0 * 100:.1f}%"
        print(f"{m:<10} | {v['days']:^5} | {v['green']}G / {v['red']}R | {v['trades']:^5} | WR: {wr:>5.1f}% | {pnl_str:>14} | {margin_roe:>10}")
    print(f"60-DAY TOTAL: INR {total_pnl:,.2f} (+{total_pnl/250:.2f}% Margin ROE)")
    return total_pnl

if __name__ == "__main__":
    for cap in [-1500.0, -1800.0]:
        test_loss_cap(cap)
