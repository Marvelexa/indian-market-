import urllib.request, json

req = urllib.request.Request(
    'http://127.0.0.1:8000/api/replay/control',
    data=json.dumps({'action': 'SET_DATE', 'targetDate': '2026-11-04', 'speed': 60}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
urllib.request.urlopen(req)

# Advance seconds
req2 = urllib.request.Request(
    'http://127.0.0.1:8000/api/replay/control',
    data=json.dumps({'action': 'SET_SECOND', 'secondOfDay': 3600}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req2) as r:
    data = json.loads(r.read())
    st = data['state']
    print('=== TIME-MACHINE REPLAY API VERIFICATION ===')
    print('Date:', st['currentDate'], '| Time:', st['formattedTime'])
    print('Active Seats Count:', len(st['activePositions']))
    for p in st['activePositions']:
        print(f"Seat: {p['symbol']} | {p['side']} | Entry: ₹{p['entryPrice']} | SL: ₹{p['slPrice']} | Stage: {p['stage']} | Milestone: {p.get('currentMilestone')} | Float: ₹{p['floatingPnlInr']}")
    print('Closed Trades Count:', len(st['closedLedger']))
    for t in st['closedLedger'][:5]:
        print(f"Closed: {t['symbol']} | PnL: ₹{t['netPnlInr']} | Reason: {t['exitReason']}")
