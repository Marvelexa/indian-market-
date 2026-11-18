import urllib.request
import json
import datetime
from zoneinfo import ZoneInfo

ist = ZoneInfo('Asia/Kolkata')
url_daily = 'https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=1d&range=1y'
req = urllib.request.Request(url_daily, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req)
data = json.loads(resp.read().decode())['chart']['result'][0]

timestamps = data['timestamp']
quote = data['indicators']['quote'][0]

bars = []
for i in range(len(timestamps)):
    dt = datetime.datetime.fromtimestamp(timestamps[i], ist)
    bars.append({
        "date": dt.strftime("%Y-%m-%d"),
        "open": quote['open'][i],
        "high": quote['high'][i],
        "low": quote['low'][i],
        "close": quote['close'][i],
        "volume": quote['volume'][i]
    })

print(f"Total Daily Bars Fetched: {len(bars)}")
print(f"First Date: {bars[0]['date']}")
print(f"Last Date:  {bars[-1]['date']}")

# Group by month for 2026
months = {}
for b in bars:
    m_key = b['date'][:7]
    if m_key not in months:
        months[m_key] = []
    months[m_key].append(b)

print("\nMonth-by-Month NIFTY Market Profile (2026):")
print(f"{'Month':<10} | {'Days':<5} | {'Open':<10} | {'Close':<10} | {'Change %':<10} | {'Range (High-Low)':<18} | {'Regime Type'}")
print("-" * 85)

for m, m_bars in sorted(months.items()):
    m_open = m_bars[0]['open']
    m_close = m_bars[-1]['close']
    chg = ((m_close - m_open) / m_open) * 100.0
    m_high = max(b['high'] for b in m_bars if b['high'] is not None)
    m_low = min(b['low'] for b in m_bars if b['low'] is not None)
    rng_pts = m_high - m_low
    rng_pct = (rng_pts / m_open) * 100.0
    
    # Classify monthly regime
    if abs(chg) >= 2.5 or rng_pct >= 5.0:
        regime = "High Momentum Trend Month (25-30%+ ROE)"
    else:
        regime = "Rangebound Chop / Mean Reversion"
    
    print(f"{m:<10} | {len(m_bars):<5} | {m_open:>9.1f} | {m_close:>9.1f} | {chg:>+8.2f}% | {rng_pts:>7.1f} pts ({rng_pct:>4.1f}%) | {regime}")
