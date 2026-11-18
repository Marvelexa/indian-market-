import requests
import re

r = requests.get('https://dummytrader.in/')
print("Status:", r.status_code)
print("Title:", re.findall(r'<title>(.*?)</title>', r.text))
scripts = re.findall(r'src=["\'](/assets/.*?\.js)["\']', r.text)
print("Scripts:", scripts)

for s in scripts:
    s_url = f"https://dummytrader.in{s}"
    s_res = requests.get(s_url)
    apis = set(re.findall(r'/api/v1/[\w/]+', s_res.text))
    print(f"\nAPIs found in {s}:")
    for a in sorted(apis):
        print("  ", a)
    # search for symbols or tickers
    symbols = set(re.findall(r'\b[A-Z]{3,12}\b', s_res.text))
    common_nse = {'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'SBIN', 'BHARTIARTL', 'ITC', 'KOTAKBANK', 'LT'}
    found_common = symbols.intersection(common_nse)
    print("Found common NSE symbols:", found_common)
