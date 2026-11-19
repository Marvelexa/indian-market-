/**
 * FILE: lib/paper/openalgoGatewayServer.ts
 * ============================================================================
 * OPENALGO PAPER TRADING GATEWAY SERVICE (PORT 5000)
 * Implements the standard OpenAlgo REST API Specification (openalgo.in)
 * in Analyzer / Paper Trading Mode for NSE/BSE/MCX F&O.
 *
 * Endpoints:
 *   - GET  /api/v1/ping
 *   - POST /api/v1/placeorder
 *   - POST /api/v1/closeposition
 *   - GET  /api/v1/positions
 *   - GET  /api/v1/orders
 *   - GET  / (Mobile & Desktop Web Terminal UI)
 * ============================================================================
 */

import http from 'http';

export interface OpenAlgoVirtualPosition {
  symbol: string;
  exchange: string;
  quantity: number;
  average_price: number;
  ltp?: number;
  pnl?: number;
  product: string;
  strategy: string;
  opened_at: string;
}

export interface OpenAlgoVirtualOrder {
  orderid: string;
  symbol: string;
  exchange: string;
  action: 'BUY' | 'SELL';
  pricetype: 'LIMIT' | 'MARKET';
  product: string;
  quantity: number;
  price: number;
  status: 'COMPLETE' | 'REJECTED' | 'CANCELLED';
  strategy: string;
  timestamp: string;
}

export class OpenAlgoGatewayServer {
  private static instance: OpenAlgoGatewayServer | null = null;
  private server: http.Server | null = null;
  private positions: Map<string, OpenAlgoVirtualPosition> = new Map();
  private orders: OpenAlgoVirtualOrder[] = [];
  private orderCounter = 1000;

  public static getInstance(): OpenAlgoGatewayServer {
    if (!this.instance) {
      this.instance = new OpenAlgoGatewayServer();
    }
    return this.instance;
  }

  public start(port = 5000): void {
    if (this.server) return;

    this.server = http.createServer((req, res) => {
      // CORS Headers for Mobile & Web clients
      res.setHeader('Access-Control-Allow-Origin', '*');
      res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
      res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

      if (req.method === 'OPTIONS') {
        res.writeHead(200);
        res.end();
        return;
      }

      const url = req.url || '';

      // 1. Health check ping
      if (url === '/api/v1/ping') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'success',
          message: 'OpenAlgo Paper Gateway Active',
          mode: 'ANALYZER',
          version: '1.0.47',
          server_time: new Date().toISOString()
        }));
        return;
      }

      // 2. Place Order
      if (url === '/api/v1/placeorder' && req.method === 'POST') {
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', () => {
          try {
            const data = JSON.parse(body || '{}');
            const sym = (data.symbol || '').toUpperCase();
            const action = (data.action || 'BUY').toUpperCase() as 'BUY' | 'SELL';
            const exchange = (data.exchange || 'NFO').toUpperCase();
            const qty = Number(data.quantity) || 1;
            const price = Number(data.price) || 0;
            const strategy = data.strategy || 'NexusBharat_Fno';
            const product = data.product || 'MIS';
            const priceType = data.pricetype || (price > 0 ? 'LIMIT' : 'MARKET');

            this.orderCounter++;
            const orderid = `OA-${Date.now()}-${this.orderCounter}`;

            const orderRecord: OpenAlgoVirtualOrder = {
              orderid,
              symbol: sym,
              exchange,
              action,
              pricetype: priceType,
              product,
              quantity: qty,
              price,
              status: 'COMPLETE',
              strategy,
              timestamp: new Date().toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' }) + ' IST'
            };
            this.orders.unshift(orderRecord);
            if (this.orders.length > 100) this.orders.pop();

            // Update virtual positions
            const posKey = `${sym}_${exchange}_${product}`;
            if (action === 'BUY') {
              const existing = this.positions.get(posKey);
              if (existing) {
                const totalQty = existing.quantity + qty;
                const totalVal = (existing.average_price * existing.quantity) + (price * qty);
                existing.quantity = totalQty;
                existing.average_price = Number((totalVal / totalQty).toFixed(2));
              } else {
                this.positions.set(posKey, {
                  symbol: sym,
                  exchange,
                  quantity: qty,
                  average_price: price,
                  product,
                  strategy,
                  opened_at: orderRecord.timestamp
                });
              }
            } else if (action === 'SELL') {
              const existing = this.positions.get(posKey);
              if (existing) {
                if (existing.quantity <= qty) {
                  this.positions.delete(posKey);
                } else {
                  existing.quantity -= qty;
                }
              }
            }

            console.log(`[OpenAlgo Gateway :5000] Order Executed: ${action} ${qty}x ${sym} @ ₹${price} (ID: ${orderid})`);

            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({
              status: 'success',
              orderid,
              message: 'Order executed successfully in Analyzer mode',
              data: { orderid, symbol: sym, quantity: qty, price, exchange }
            }));
          } catch (e: any) {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ status: 'error', message: e.message }));
          }
        });
        return;
      }

      // 3. Close Position
      if (url === '/api/v1/closeposition' && req.method === 'POST') {
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', () => {
          try {
            const data = JSON.parse(body || '{}');
            const sym = (data.symbol || '').toUpperCase();
            const exchange = (data.exchange || 'NFO').toUpperCase();
            const posKey = `${sym}_${exchange}_MIS`;

            if (this.positions.has(posKey)) {
              this.positions.delete(posKey);
            } else {
              // Try prefix match
              for (const [key] of this.positions.entries()) {
                if (key.startsWith(sym)) {
                  this.positions.delete(key);
                  break;
                }
              }
            }

            console.log(`[OpenAlgo Gateway :5000] Position Closed: ${sym} on ${exchange}`);
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ status: 'success', message: 'Position closed successfully' }));
          } catch (e: any) {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ status: 'error', message: e.message }));
          }
        });
        return;
      }

      // 4. Query Positions
      if (url.startsWith('/api/v1/positions')) {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'success',
          data: Array.from(this.positions.values())
        }));
        return;
      }

      // 5. Query Orders
      if (url.startsWith('/api/v1/orders')) {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'success',
          data: this.orders
        }));
        return;
      }

      // 6. Mobile & Desktop Web Terminal Dashboard
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(this.renderDashboardHtml());
    });

    this.server.listen(port, '0.0.0.0', () => {
      console.log(`===========================================================================`);
      console.log(`🚀 OPENALGO PAPER GATEWAY (ANALYZER) ACTIVE ON PORT ${port}`);
      console.log(`   Desktop UI: http://localhost:${port}`);
      console.log(`   Mobile UI:  http://192.168.1.4:${port}`);
      console.log(`   Mode:       ANALYZER (Zero-Risk Simulated Broker Execution)`);
      console.log(`===========================================================================`);
    });
  }

  public stop(): void {
    if (this.server) {
      this.server.close();
      this.server = null;
    }
  }

  private renderDashboardHtml(): string {
    const posList = Array.from(this.positions.values());
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>OpenAlgo Terminal — Paper Trading Analyzer</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0c1017; color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; padding: 16px; }
    header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 16px; border-bottom: 1px solid #1e293b; margin-bottom: 16px; }
    .brand { display: flex; align-items: center; gap: 10px; }
    .logo { width: 32px; height: 32px; background: #3b82f6; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 900; color: #fff; font-size: 18px; }
    h1 { font-size: 18px; font-weight: 700; color: #f8fafc; }
    .status-badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 20px; color: #10b981; font-size: 12px; font-weight: 600; }
    .dot { width: 8px; height: 8px; background: #10b981; border-radius: 50%; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }
    .card { background: #151d2c; border: 1px solid #1e293b; border-radius: 10px; padding: 14px; }
    .card-title { font-size: 11px; text-transform: uppercase; color: #94a3b8; font-weight: 700; letter-spacing: 0.5px; }
    .card-value { font-size: 20px; font-weight: 800; margin-top: 4px; color: #38bdf8; }
    .card-sub { font-size: 11px; color: #64748b; margin-top: 2px; }
    .section-title { font-size: 14px; font-weight: 700; color: #e2e8f0; margin: 16px 0 8px 0; display: flex; justify-content: space-between; align-items: center; }
    .table-container { background: #151d2c; border: 1px solid #1e293b; border-radius: 10px; overflow-x: auto; margin-bottom: 20px; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: left; }
    th { background: #1e293b; color: #94a3b8; padding: 10px 12px; font-weight: 600; text-transform: uppercase; font-size: 10px; }
    td { padding: 10px 12px; border-bottom: 1px solid #1e293b; white-space: nowrap; }
    tr:last-child td { border-bottom: none; }
    .badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-weight: 700; font-size: 10px; }
    .badge-buy { background: rgba(16, 185, 129, 0.2); color: #10b981; }
    .badge-sell { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
    .badge-nfo { background: rgba(56, 189, 248, 0.15); color: #38bdf8; }
    .empty-state { text-align: center; color: #64748b; padding: 24px; font-size: 13px; }
    .btn-refresh { background: #3b82f6; color: #fff; border: none; padding: 6px 12px; border-radius: 6px; font-size: 11px; font-weight: 700; cursor: pointer; }
    .mobile-tip { background: #1e293b; border-left: 3px solid #38bdf8; padding: 10px 12px; border-radius: 4px; font-size: 12px; color: #cbd5e1; margin-bottom: 16px; }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="logo">⚡</div>
      <div>
        <h1>OpenAlgo Terminal</h1>
        <div style="font-size: 11px; color: #94a3b8;">Analyzer Mode (Paper Trading)</div>
      </div>
    </div>
    <div class="status-badge">
      <span class="dot"></span> 1000ms Live
    </div>
  </header>

  <div class="mobile-tip">
    📱 <strong>Mobile Access:</strong> Open <code>http://192.168.1.4:5000</code> in your phone's browser while on the same Wi-Fi.
  </div>

  <div class="grid">
    <div class="card">
      <div class="card-title">Trading Mode</div>
      <div class="card-value" style="color: #10b981;">ANALYZER</div>
      <div class="card-sub">Zero-Risk Paper Trading</div>
    </div>
    <div class="card">
      <div class="card-title">Open Positions</div>
      <div class="card-value" id="pos-count">${posList.length}</div>
      <div class="card-sub">Active Virtual Contracts</div>
    </div>
    <div class="card">
      <div class="card-title">Total Orders</div>
      <div class="card-value" id="order-count">${this.orders.length}</div>
      <div class="card-sub">Engine Dispatched</div>
    </div>
    <div class="card">
      <div class="card-title">Strategy</div>
      <div class="card-value" style="font-size: 16px; color: #a78bfa;">NexusBharat_Fno</div>
      <div class="card-sub">NSE/BSE/MCX F&O</div>
    </div>
  </div>

  <div class="section-title">
    <span>📊 Open Positions (${posList.length})</span>
    <button class="btn-refresh" onclick="location.reload()">Refresh</button>
  </div>
  <div class="table-container">
    <table>
      <thead>
        <tr>
          <th>Symbol</th>
          <th>Exchange</th>
          <th>Qty</th>
          <th>Avg Price</th>
          <th>Strategy</th>
          <th>Opened At</th>
        </tr>
      </thead>
      <tbody id="positions-tbody">
        ${posList.length === 0 ? '<tr><td colspan="6" class="empty-state">No open positions in Analyzer mode. Bot scanner is active.</td></tr>' :
          posList.map(p => `
            <tr>
              <td><strong>${p.symbol}</strong></td>
              <td><span class="badge badge-nfo">${p.exchange}</span></td>
              <td>${p.quantity}</td>
              <td>₹${p.average_price.toFixed(2)}</td>
              <td>${p.strategy}</td>
              <td style="color: #94a3b8;">${p.opened_at}</td>
            </tr>
          `).join('')}
      </tbody>
    </table>
  </div>

  <div class="section-title">
    <span>📋 Order Execution Log (${this.orders.length})</span>
  </div>
  <div class="table-container">
    <table>
      <thead>
        <tr>
          <th>Order ID</th>
          <th>Time</th>
          <th>Action</th>
          <th>Symbol</th>
          <th>Exchange</th>
          <th>Qty</th>
          <th>Price</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody id="orders-tbody">
        ${this.orders.length === 0 ? '<tr><td colspan="8" class="empty-state">No orders placed yet. Orders from NexusBharat engine will appear here.</td></tr>' :
          this.orders.slice(0, 15).map(o => `
            <tr>
              <td style="color: #38bdf8; font-family: monospace;">${o.orderid}</td>
              <td style="color: #94a3b8;">${o.timestamp}</td>
              <td><span class="badge ${o.action === 'BUY' ? 'badge-buy' : 'badge-sell'}">${o.action}</span></td>
              <td><strong>${o.symbol}</strong></td>
              <td><span class="badge badge-nfo">${o.exchange}</span></td>
              <td>${o.quantity}</td>
              <td>₹${o.price.toFixed(2)}</td>
              <td><span style="color: #10b981; font-weight: 700;">${o.status}</span></td>
            </tr>
          `).join('')}
      </tbody>
    </table>
  </div>

  <script>
    // 2-Second auto refresh loop
    setInterval(async () => {
      try {
        const [posRes, ordRes] = await Promise.all([
          fetch('/api/v1/positions'),
          fetch('/api/v1/orders')
        ]);
        if (posRes.ok && ordRes.ok) {
          const posData = await posRes.json();
          const ordData = await ordRes.json();
          document.getElementById('pos-count').innerText = (posData.data || []).length;
          document.getElementById('order-count').innerText = (ordData.data || []).length;
        }
      } catch (e) {}
    }, 2000);
  </script>
</body>
</html>`;
  }
}
