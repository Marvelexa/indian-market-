// File: scripts/verify_time_machine_november.ts
import { TimeMachineReplayEngine, type ReplayClosedTrade } from '../lib/replay/timeMachineReplayEngine.ts';

async function run() {
  console.log('='.repeat(90));
  console.log('🏛️ RUNNING OFFICIAL TIMEMACHINE REPLAY ENGINE AUDIT (1-NOV TO 18-NOV-2026)');
  console.log('   Strict TypeScript Production Engine: Zero-Look-Ahead, -₹1,800 SL, -₹4,500 Daily Breaker, ₹55 Taxes');
  console.log('='.repeat(90));

  const engine = TimeMachineReplayEngine.getInstance();
  await engine.initialize();
  engine.pause(); // Pause auto-interval timer to step manually

  const state = engine.getState();
  const totalBars = state.totalBars;
  console.log(`Starting stepping through ${totalBars} bars...`);

  // Step from initial barIndex to totalBars - 1
  for (let b = 45; b < totalBars; b++) {
    for (let sub = 0; sub < 4; sub++) {
      engine.stepSubTick();
    }
  }

  const finalState = engine.getState();
  const closedTrades: ReplayClosedTrade[] = finalState.closedLedger || [];

  // Filter November trades
  const novTrades = closedTrades.filter((t) => {
    const d = t.exitDateFormatted || t.entryDateFormatted || '';
    return d.includes('Nov 2026');
  });

  console.log(`\nCompleted! Found ${novTrades.length} closed trades in November.\n`);

  // Group by date
  const dayMap: Map<string, { trades: ReplayClosedTrade[]; gross: number; net: number; wins: number; losses: number }> = new Map();

  for (const t of novTrades) {
    const dStr = t.exitDateFormatted ? t.exitDateFormatted.split(',')[0] : 'Unknown';
    if (!dayMap.has(dStr)) {
      dayMap.set(dStr, { trades: [], gross: 0, net: 0, wins: 0, losses: 0 });
    }
    const dRec = dayMap.get(dStr)!;
    dRec.trades.push(t);
    dRec.net += t.netPnlInr;
    dRec.gross += t.netPnlInr + 55;
    if (t.netPnlInr >= 0) dRec.wins++;
    else dRec.losses++;
  }

  console.log('='.repeat(110));
  console.log('📅 TIMEMACHINE REPLAY ENGINE — NOVEMBER 2026 DAY-BY-DAY VERIFIED LEDGER');
  console.log('='.repeat(110));
  console.log('Date'.padEnd(16) + 'Trades'.padEnd(10) + 'Wins'.padEnd(8) + 'Losses'.padEnd(10) + 'WinRate'.padEnd(12) + 'Gross PnL'.padEnd(15) + 'Taxes'.padEnd(12) + 'Net Realized PnL');
  console.log('\n--- DETAILED TRADE LIST ---');
  for (const t of novTrades) {
    console.log(`${t.exitDateFormatted} | ${t.symbol} | ${t.side} | Qty:${t.quantity} | Entry:₹${t.entryPrice} -> Exit:₹${t.exitPrice} | Net:₹${t.netPnlInr} | ${t.exitReason}`);
  }
  console.log('---------------------------\n');

  console.log('-'.repeat(110));

  let totTrades = 0;
  let totWins = 0;
  let totLosses = 0;
  let totGross = 0;
  let totNet = 0;

  for (const [day, data] of Array.from(dayMap.entries()).sort()) {
    totTrades += data.trades.length;
    totWins += data.wins;
    totLosses += data.losses;
    totGross += data.gross;
    totNet += data.net;

    const wr = data.trades.length > 0 ? ((data.wins / data.trades.length) * 100).toFixed(1) + '%' : 'N/A';
    const netStr = data.net >= 0 ? `+₹${data.net.toLocaleString()}` : `-₹${Math.abs(data.net).toLocaleString()}`;
    const grossStr = data.gross >= 0 ? `+₹${data.gross.toLocaleString()}` : `-₹${Math.abs(data.gross).toLocaleString()}`;

    console.log(
      day.padEnd(16) +
      String(data.trades.length).padEnd(10) +
      String(data.wins).padEnd(8) +
      String(data.losses).padEnd(10) +
      wr.padEnd(12) +
      grossStr.padEnd(15) +
      `-₹${data.trades.length * 55}`.padEnd(12) +
      netStr
    );
  }

  console.log('\n--- DETAILED TRADE LIST ---');
  for (const t of novTrades) {
    console.log(`${t.exitDateFormatted} | ${t.symbol} | ${t.side} | Qty:${t.quantity} | Entry:₹${t.entryPrice} -> Exit:₹${t.exitPrice} | Net:₹${t.netPnlInr} | ${t.exitReason}`);
  }
  console.log('---------------------------\n');

  console.log('-'.repeat(110));
  console.log(`TOTALS: Trades: ${totTrades} | Wins: ${totWins} | Losses: ${totLosses} | Win Rate: ${((totWins / totTrades) * 100).toFixed(1)}%`);
  console.log(`Gross Realized: ₹${totGross.toLocaleString()} | Statutory Friction (₹55/trd): -₹${totTrades * 55}`);
  console.log(`🏆 TRUE NET REALIZED NOVEMBER P&L: ₹${totNet.toLocaleString()} (${((totNet / 100000) * 100).toFixed(2)}% ROI on ₹1,00,000 Capital)`);
  console.log('='.repeat(110));
}

run().catch(console.error);
