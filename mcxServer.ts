/**
 * FILE: mcxServer.ts
 * ============================================================================
 * MCX COMMODITY 15M S&R + 5M OPTION SNIPER DAEMON (09:00 AM - 11:30 PM IST)
 * Dedicated High-Frequency Quantitative Execution Engine for:
 *   - CRUDEOIL (Lot 100, Step 50)
 *   - NATURALGAS (Lot 1250, Step 2.5)
 *   - GOLD (Lot 1, Step 100)
 *   - SILVER (Lot 1, Step 500)
 *   - COPPER (Lot 2500, Step 5)
 *
 * Rules:
 *   - Session hours: 09:00 AM to 11:30 PM IST
 *   - Mandatory Auto Square-Off: 11:20 PM IST
 *   - Pure Option Buying ONLY (BUY ATM CE on 15m Support Bounce / BUY ATM PE on 15m Res Rejection)
 *   - Hard SL: Strictly -₹2,500 per lot
 *   - 5-Stage Trailing Ladder: +₹500 -> +₹1,000 -> +₹2,000 -> +₹4,000 -> +₹8,000+ Runner
 * Exposes live status API & Dashboard on http://127.0.0.1:3006
 * ============================================================================
 */

import http from 'http';
import {
  McxCommodityOptionSniperEngine,
  type McxCandle,
  type McxSignalResult,
  type ActiveMcxOptionPosition,
  type ClosedMcxTrade
} from './lib/mcx/mcxCommodityOptionSniperEngine.ts';

const PY_BACKEND_URL = 'http://127.0.0.1:8000';
const PORT = 3006;

const mcxSniper = new McxCommodityOptionSniperEngine();

// In-Memory Market Data Cache for MCX
let mcxCandles5m: Record<string, McxCandle[]> = {};
let mcxCandles15m: Record<string, McxCandle[]> = {};
let mcxLiveLtpMap: Record<string, number> = {};
let mcxSrMatrix: Record<string, McxSignalResult> = {};

let isFetchingCandles = false;
let cycleCounter = 0;
let mtfApprovedCount = 0;
let mtfVetoCount = 0;

/**
 * Cleanly aggregates 5-minute candles into 15-minute candles.
 * Aligns to 15-minute clock boundaries (900,000 ms).
 */
export function aggregateMcx5mTo15m(candles5m: McxCandle[]): McxCandle[] {
  if (!candles5m || candles5m.length === 0) return [];
  const buckets: Map<number, McxCandle[]> = new Map();

  for (const c of candles5m) {
    if (!c || !c.timestamp || c.close <= 0) continue;
    const bucketKey = Math.floor(c.timestamp / 900000) * 900000;
    const existing = buckets.get(bucketKey);
    if (!existing) {
      buckets.set(bucketKey, [c]);
    } else {
      existing.push(c);
    }
  }

  const result15m: McxCandle[] = [];
  for (const [timestamp, group] of buckets.entries()) {
    if (group.length === 0) continue;
    const open = group[0].open;
    const high = Math.max(...group.map((c) => c.high));
    const low = Math.min(...group.map((c) => c.low));
    const close = group[group.length - 1].close;
    const volume = group.reduce((sum, c) => sum + (c.volume || 0), 0);
    result15m.push({ timestamp, open, high, low, close, volume });
  }

  return result15m.sort((a, b) => a.timestamp - b.timestamp);
}

function getIstClock(): { istStr: string; minutes: number; isMarketOpen: boolean } {
  const ist = new Date(Date.now() + 5.5 * 3600000);
  const hh = ist.getUTCHours();
  const mm = ist.getUTCMinutes();
  const ss = ist.getUTCSeconds();
  const minutes = hh * 60 + mm;
  const istStr = `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')} IST`;
  // MCX is open from 09:00 AM (540 min) to 11:30 PM (1410 min)
  const isMarketOpen = minutes >= 9 * 60 && minutes <= 23 * 60 + 30;
  return { istStr, minutes, isMarketOpen };
}

// ============================================================================
// 1. REFRESH MCX BATCH 5M CANDLES & GENERATE 15M S&R CANDLES
// ============================================================================
async function refreshMcxCandles(): Promise<void> {
  if (isFetchingCandles) return;
  isFetchingCandles = true;
  try {
    const res = await fetch(`${PY_BACKEND_URL}/api/mcx/candles-batch`, {
      signal: AbortSignal.timeout(20000),
    });
    if (!res.ok) {
      console.error(`[MCX Daemon] Failed to fetch candles-batch: HTTP ${res.status}`);
      isFetchingCandles = false;
      return;
    }
    const data = (await res.json()) as Record<string, McxCandle[]>;

    for (const sym of Object.keys(McxCommodityOptionSniperEngine.MCX_WHITELIST)) {
      const candles = data[sym];
      if (candles && candles.length > 0) {
        mcxCandles5m[sym] = candles;
        mcxCandles15m[sym] = aggregateMcx5mTo15m(candles);
        const last = candles[candles.length - 1];
        if (last) {
          mcxLiveLtpMap[sym] = last.close;
        }
      }
    }
  } catch (err: any) {
    console.error(`[MCX Daemon] Error refreshing candles: ${err.message}`);
  } finally {
    isFetchingCandles = false;
  }
}

// ============================================================================
// 2. MASTER 1500MS EXECUTION CYCLE FOR MCX
// ============================================================================
async function runMcxCycle(): Promise<void> {
  cycleCounter++;
  const { istStr, minutes, isMarketOpen } = getIstClock();

  // 1. Refresh candles every 30 seconds (every 20 cycles) or on startup
  if (cycleCounter % 20 === 1 || Object.keys(mcxCandles5m).length === 0) {
    await refreshMcxCandles();
  }

  // 2. Update synthetic option tick prices (0.55 delta)
  for (const pos of mcxSniper.getActivePositions()) {
    const spot = mcxLiveLtpMap[pos.commoditySymbol];
    if (spot) {
      const delta = 0.55;
      const spotMove = pos.optionType === 'CE' ? spot - pos.strike : pos.strike - spot;
      const dynPrem = Math.max(0.1, Number((pos.entryPremium + spotMove * delta * 0.15).toFixed(2)));
      mcxLiveLtpMap[pos.optionSymbol] = dynPrem;
    }
  }

  // 3. Evaluate active positions for TP1/TP2/Ladder/Hard SL/11:20 PM Square-Off
  await mcxSniper.evaluateOpenPositionsTick({
    livePremiumMap: mcxLiveLtpMap,
    sendBrokerExit: async (order) => {
      console.log(
        `\n🎯 [MCX OPTION EXIT] ${order.side} ${order.qty}x ${order.optionSymbol} @ ₹${order.price} | Tag: ${order.tag}`
      );
    },
  });

  // 4. Run 15m S&R + 5m Sniper setup evaluation across 5 commodities
  if (cycleCounter % 20 === 1 || cycleCounter === 1) {
    for (const [sym, cfg] of Object.entries(McxCommodityOptionSniperEngine.MCX_WHITELIST)) {
      const c5m = mcxCandles5m[sym] || [];
      const c15m = mcxCandles15m[sym] || [];

      if (c5m.length >= 40 && c15m.length >= 24) {
        const decision = McxCommodityOptionSniperEngine.evaluateSetup({
          commoditySymbol: sym,
          candles15m: c15m,
          candles5m: c5m,
        });
        mcxSrMatrix[sym] = decision;

        // Only fire live broker entries when market is open (09:00 AM to 11:15 PM IST)
        if (decision.approved && isMarketOpen && minutes < 23 * 60 + 15) {
          mtfApprovedCount++;
          console.log(
            `\n🎯 [MCX 15M S&R APPROVED] ${decision.commoditySymbol} -> ${decision.action} | ` +
              `Strike: ${decision.atmStrike} | Pattern: ${decision.patternTag} | ` +
              `Reason: ${decision.reason} | RR: ${decision.riskRewardRatio} | MaxRisk: -₹${decision.maxRiskInr}`
          );

          // Execute pure option buying entry
          const spotLtp = mcxLiveLtpMap[sym] || decision.underlyingLtp;
          const res = await mcxSniper.executeOptionEntry({
            decision,
            currentExpiryCode: '26NOV',
            getOptionPremium: async (optSym) => {
              if (mcxLiveLtpMap[optSym] && mcxLiveLtpMap[optSym] > 0) return mcxLiveLtpMap[optSym];
              // Standard ATM option premium ~2.0% of spot
              const prem = Number((spotLtp * 0.02).toFixed(2));
              mcxLiveLtpMap[optSym] = prem;
              return prem;
            },
            sendBrokerOrder: async (order) => {
              console.log(
                `\n⚡ [MCX BROKER ORDER] ${order.side} ${order.qty}x ${order.optionSymbol} @ ₹${order.price} | Tag: ${order.tag}`
              );
            },
          });

          if (res.status === 'ORDER_FIRED' && res.position) {
            console.log(
              `\n🚀 [MCX POSITION OPENED] ${res.position.optionSymbol} | Lot: ${res.position.lotSize} | ` +
                `Entry: ₹${res.position.entryPremium} | Hard SL: ₹${res.position.currentSlPremium} (-₹2,500 Risk)`
            );
          }
        } else {
          mtfVetoCount++;
        }
      }
    }
  }

  // 5. Periodic status log every 10 cycles
  if (cycleCounter % 10 === 0) {
    const active = mcxSniper.getActivePositions().length;
    const closed = mcxSniper.getClosedTrades().length;
    console.log(
      `[${istStr}] 🛢️ MCX COMMODITY DAEMON | Session: ${isMarketOpen ? '🟢 OPEN (09:00-23:30)' : '🔴 CLOSED'} | ` +
        `Active Lots: ${active} | Closed Trades: ${closed} | ` +
        `Commodities Loaded: ${Object.keys(mcxCandles5m).length}/5 | Cycle #${cycleCounter}`
    );
  }
}

// Start master MCX loop
async function startMcxDaemon(): Promise<void> {
  console.log('='.repeat(80));
  console.log('  🛢️ MCX COMMODITY 15M S&R + 5M OPTION SNIPER DAEMON STARTING (1500ms LOOP)');
  console.log('  Universe: CRUDEOIL, NATURALGAS, GOLD, SILVER, COPPER');
  console.log(`  Targeting API: ${PY_BACKEND_URL}`);
  console.log(`  Telemetry Server: http://127.0.0.1:${PORT}`);
  console.log('='.repeat(80));

  console.log('[MCX Daemon] Pre-loading 5m batch candles & live prices...');
  await refreshMcxCandles();

  console.log(`[MCX Daemon] Ready with ${Object.keys(mcxCandles5m).length} commodities loaded.`);
  await runMcxCycle();

  setInterval(runMcxCycle, 1500);
}

// Only launch daemon if executed directly
const isMain = process.argv[1] && (process.argv[1].endsWith('mcxServer.ts') || process.argv[1].endsWith('mcxServer.js'));
if (isMain) {
  startMcxDaemon();
}

// ============================================================================
// 3. TELEMETRY HTTP SERVER (http://127.0.0.1:3006)
// ============================================================================
const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');

  const { istStr, isMarketOpen } = getIstClock();
  const activePositions = mcxSniper.getActivePositions();
  const closedTrades = mcxSniper.getClosedTrades();
  const approvedList = Object.values(mcxSrMatrix).filter((d) => d.approved);

  if (req.url === '/api/mcx/status') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(
      JSON.stringify(
        {
          success: true,
          daemon: 'MCX_COMMODITY_OPTION_SNIPER',
          istTimeStr: istStr,
          isMarketOpen,
          sessionHours: '09:00 AM - 11:30 PM IST',
          autoSquareOffTime: '11:20 PM IST',
          commoditiesTracked: Object.keys(McxCommodityOptionSniperEngine.MCX_WHITELIST),
          activePositions,
          closedTrades,
          sr15mMatrix: mcxSrMatrix,
          stats: {
            activeLots: activePositions.length,
            closedTradesCount: closedTrades.length,
            approvedSetupsCount: approvedList.length,
            vetoCount: mtfVetoCount,
          },
        },
        null,
        2
      )
    );
    return;
  }

  if (req.url === '/api/mcx/sr-matrix') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(
      JSON.stringify(
        {
          success: true,
          istTimeStr: istStr,
          srMatrix: mcxSrMatrix,
        },
        null,
        2
      )
    );
    return;
  }

  // Dashboard HTML
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  const totalNetPnl = closedTrades.reduce((sum, t) => sum + t.netPnlInr, 0);

  res.end(`<!DOCTYPE html>
<html>
<head>
  <title>MCX COMMODITY — 15M S&R + 5M Option Sniper Terminal</title>
  <meta http-equiv="refresh" content="2">
  <style>
    body { background: #0a0e17; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; }
    h1 { color: #f59e0b; font-size: 20px; margin-bottom: 4px; }
    .subtitle { color: #94a3b8; font-size: 13px; margin-bottom: 20px; }
    .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
    .card { background: #131b2e; border: 1px solid #1e293b; border-radius: 8px; padding: 14px; }
    .label { color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }
    .val { font-size: 20px; font-weight: bold; margin-top: 4px; }
    .green { color: #10b981; }
    .red { color: #ef4444; }
    .amber { color: #f59e0b; }
    .cyan { color: #38bdf8; }
    table { width: 100%; border-collapse: collapse; background: #131b2e; border-radius: 8px; overflow: hidden; margin-bottom: 20px; }
    th, td { padding: 10px 14px; text-align: left; font-size: 13px; border-bottom: 1px solid #1e293b; }
    th { background: #1e293b; color: #94a3b8; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .badge-bull { background: rgba(16,185,129,0.2); color: #10b981; }
    .badge-bear { background: rgba(239,68,68,0.2); color: #ef4444; }
    .badge-neutral { background: rgba(148,163,184,0.2); color: #94a3b8; }
  </style>
</head>
<body>
  <h1>🛢️ MCX COMMODITY — 15M S&R + 5M Option Sniper Terminal</h1>
  <div class="subtitle">Crude Oil, Natural Gas, Gold, Silver & Copper • Session: 09:00 AM - 11:30 PM IST • Auto Square-Off: 11:20 PM</div>

  <div class="grid">
    <div class="card">
      <div class="label">IST Clock / Session</div>
      <div class="val amber">${istStr}</div>
      <div style="font-size:11px; color:#94a3b8; margin-top:4px;">${isMarketOpen ? '🟢 ACTIVE MARKET SESSION' : '🔴 MARKET CLOSED'}</div>
    </div>
    <div class="card">
      <div class="label">15M S&R Scan Status</div>
      <div class="val green">${approvedList.length} Approved</div>
      <div style="font-size:11px; color:#94a3b8; margin-top:4px;">Tracked: 5 Commodities | Vetoed Mid-Range: ${mtfVetoCount}</div>
    </div>
    <div class="card">
      <div class="label">Active Commodity Positions</div>
      <div class="val cyan">${activePositions.length} Lots</div>
      <div style="font-size:11px; color:#94a3b8; margin-top:4px;">Hard SL: -₹2,500/lot | Closed: ${closedTrades.length}</div>
    </div>
    <div class="card">
      <div class="label">Total Realized Net PnL</div>
      <div class="val ${totalNetPnl >= 0 ? 'green' : 'red'}">
        ${totalNetPnl >= 0 ? '+' : ''}₹${totalNetPnl.toFixed(2)}
      </div>
      <div style="font-size:11px; color:#94a3b8; margin-top:4px;">Square-Off: 11:20 PM IST (Zero Overnight)</div>
    </div>
  </div>

  <h2 style="font-size:15px; color:#f59e0b; margin-bottom:8px;">🏛️ MCX 15-Minute Support & Resistance Matrix</h2>
  <table>
    <thead>
      <tr>
        <th>Commodity</th>
        <th>LTP</th>
        <th>15m Range Pos</th>
        <th>Major Support</th>
        <th>Major Resistance</th>
        <th>Action</th>
        <th>Strike Step</th>
        <th>Lot Size</th>
        <th>Pattern / Trigger</th>
      </tr>
    </thead>
    <tbody>
      ${Object.entries(McxCommodityOptionSniperEngine.MCX_WHITELIST).map(([sym, cfg]) => {
        const d = mcxSrMatrix[sym];
        const ltp = mcxLiveLtpMap[sym] || 0;
        return `
          <tr>
            <td><strong>${sym}</strong></td>
            <td><strong>₹${ltp.toFixed(2)}</strong></td>
            <td>${d?.sr15m?.rangePosPct ? (d.sr15m.rangePosPct * 100).toFixed(0) + '%' : '--'}</td>
            <td style="color:#10b981;">₹${d?.sr15m?.majorSupport ? d.sr15m.majorSupport.toFixed(2) : '--'}</td>
            <td style="color:#ef4444;">₹${d?.sr15m?.majorResistance ? d.sr15m.majorResistance.toFixed(2) : '--'}</td>
            <td><span class="badge ${d?.action === 'BUY_ATM_CE' ? 'badge-bull' : d?.action === 'BUY_ATM_PE' ? 'badge-bear' : 'badge-neutral'}">${d?.action || 'WAIT'}</span></td>
            <td>${cfg.strikeStep}</td>
            <td>${cfg.lotSize}</td>
            <td>${d?.patternTag || 'SCANNING_NOISE'}</td>
          </tr>
        `;
      }).join('')}
    </tbody>
  </table>

  <h2 style="font-size:15px; color:#38bdf8; margin-bottom:8px;">⚡ Active MCX Option Positions (Trailing Ladder Active)</h2>
  <table>
    <thead>
      <tr>
        <th>Option Symbol</th>
        <th>Type</th>
        <th>Strike</th>
        <th>Lot Size</th>
        <th>Entry Premium</th>
        <th>Current Premium</th>
        <th>Current SL</th>
        <th>Stage</th>
        <th>Locked Profit</th>
        <th>Unrealized PnL</th>
      </tr>
    </thead>
    <tbody>
      ${activePositions.length === 0 ? '<tr><td colspan="10" style="text-align:center; color:#64748b; padding:16px;">No active MCX option positions. Waiting for 15m S&R institutional confirmation.</td></tr>' :
        activePositions.map(p => `
          <tr>
            <td><strong class="cyan">${p.optionSymbol}</strong></td>
            <td><span class="badge ${p.optionType === 'CE' ? 'badge-bull' : 'badge-bear'}">${p.optionType}</span></td>
            <td>₹${p.strike}</td>
            <td>${p.lotSize}</td>
            <td>₹${p.entryPremium.toFixed(2)}</td>
            <td>₹${p.currentPremium.toFixed(2)}</td>
            <td style="color:#ef4444;">₹${p.currentSlPremium.toFixed(2)}</td>
            <td><span class="cyan">Stage ${p.ladderStage}</span></td>
            <td>₹${p.lockedProfitInr}</td>
            <td class="${p.unrealizedPnlInr >= 0 ? 'green' : 'red'}"><strong>₹${p.unrealizedPnlInr.toFixed(2)}</strong></td>
          </tr>
        `).join('')}
    </tbody>
  </table>
</body>
</html>`);
});

if (isMain) {
  server.listen(PORT, () => {
    console.log(`[MCX Server] Live Telemetry Dashboard running at http://127.0.0.1:${PORT}`);
  });
}
