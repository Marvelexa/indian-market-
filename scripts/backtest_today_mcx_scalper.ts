import fs from 'fs';
import path from 'path';
import { McxAntiGravityScalperEngine, type McxScalpCandle } from '../lib/mcx/mcxAntiGravityScalperEngine.ts';

interface BacktestTrade {
  date: string;
  symbol: string;
  action: 'BUY' | 'SELL';
  mode: string;
  patternTag: string;
  entryTime: string;
  entryPrice: number;
  exitTime: string;
  exitPrice: number;
  exitReason: string;
  points: number;
  lots: number;
  pnlInr: number;
  maxRiskInr: number;
  rrRatio: number;
}

const SYMBOL_CONFIG: { symbol: string; rawFile: string }[] = [
  { symbol: 'CRUDEOIL', rawFile: 'CRUDEOIL.json' },
  { symbol: 'NATURALGAS', rawFile: 'NATURALGAS.json' },
  { symbol: 'NATGASMINI', rawFile: 'NATURALGAS.json' },
  { symbol: 'GOLDM', rawFile: 'GOLD.json' },
  { symbol: 'SILVERM', rawFile: 'SILVER.json' },
  { symbol: 'COPPER', rawFile: 'COPPER.json' },
];

async function runBacktest() {
  console.log('========================================================================================');
  console.log('📊 MCX "ANTI-GRAVITY" MULTI-COMMODITY SCALPER — REAL-MARKET AUDIT (12 to 17 NOV 2026)');
  console.log('========================================================================================');

  const cacheDir = path.resolve('scratch/mcx_real_data');
  const allTrades: BacktestTrade[] = [];

  for (const item of SYMBOL_CONFIG) {
    const sym = item.symbol;
    const spec = McxAntiGravityScalperEngine.PRODUCT_SPECS[sym];
    if (!spec) continue;

    const filePath = path.join(cacheDir, item.rawFile);
    if (!fs.existsSync(filePath)) {
      console.warn(`[WARN] Missing data file: ${filePath}`);
      continue;
    }

    const rawData = JSON.parse(fs.readFileSync(filePath, 'utf-8')) as McxScalpCandle[];
    const candles = rawData.filter((c) => c && c.close > 0 && c.high >= c.low);
    if (candles.length < 50) continue;

    let activePos: {
      action: 'BUY' | 'SELL';
      mode: string;
      patternTag: string;
      entryDate: string;
      entryTime: string;
      entryPrice: number;
      slPrice: number;
      tp1Price: number;
      tp2Price: number;
      maxRiskInr: number;
      rrRatio: number;
      tp1Hit: boolean;
    } | null = null;

    let lastExitIndex = -999;

    for (let i = 40; i < candles.length; i++) {
      const c = candles[i];
      // Convert timestamp to IST (UTC+5:30)
      const d = new Date(c.timestamp + 5.5 * 3600 * 1000);
      const isoStr = d.toISOString();
      const dateStr = isoStr.slice(0, 10);
      const timeStr = isoStr.slice(11, 16);
      const [h, m] = timeStr.split(':').map(Number);
      const mins = h * 60 + m;

      // Session hours: 09:15 to 23:20 IST
      const isSession = mins >= 9 * 60 + 15 && mins <= 23 * 60 + 20;

      // 1. Evaluate open position exit
      if (activePos) {
        let closed = false;
        let exitPrice = 0;
        let exitReason = '';

        if (activePos.action === 'BUY') {
          if (c.low <= activePos.slPrice) {
            exitPrice = activePos.slPrice;
            exitReason = activePos.tp1Hit ? 'TRAILED_SL_HIT' : 'INITIAL_SL_HIT';
            closed = true;
          } else if (c.high >= activePos.tp2Price) {
            exitPrice = activePos.tp2Price;
            exitReason = 'TP2_RUNNER_TARGET_HIT';
            closed = true;
          } else if (c.high >= activePos.tp1Price && !activePos.tp1Hit) {
            activePos.tp1Hit = true;
            activePos.slPrice = Number((activePos.entryPrice + spec.tickSize * 2).toFixed(2));
          }
        } else {
          // SELL
          if (c.high >= activePos.slPrice) {
            exitPrice = activePos.slPrice;
            exitReason = activePos.tp1Hit ? 'TRAILED_SL_HIT' : 'INITIAL_SL_HIT';
            closed = true;
          } else if (c.low <= activePos.tp2Price) {
            exitPrice = activePos.tp2Price;
            exitReason = 'TP2_RUNNER_TARGET_HIT';
            closed = true;
          } else if (c.low <= activePos.tp1Price && !activePos.tp1Hit) {
            activePos.tp1Hit = true;
            activePos.slPrice = Number((activePos.entryPrice - spec.tickSize * 2).toFixed(2));
          }
        }

        // Auto square-off at 23:20 IST
        if (!closed && mins >= 23 * 60 + 20) {
          exitPrice = c.close;
          exitReason = 'AUTO_SQUARE_OFF_1120PM';
          closed = true;
        }

        if (closed) {
          const points =
            activePos.action === 'BUY'
              ? Number((exitPrice - activePos.entryPrice).toFixed(2))
              : Number((activePos.entryPrice - exitPrice).toFixed(2));

          const pnlInr = Number(
            (points * spec.pointValueInr * spec.recommendedLots).toFixed(2)
          );

          allTrades.push({
            date: activePos.entryDate,
            symbol: sym,
            action: activePos.action,
            mode: activePos.mode,
            patternTag: activePos.patternTag,
            entryTime: activePos.entryTime,
            entryPrice: activePos.entryPrice,
            exitTime: timeStr,
            exitPrice: Number(exitPrice.toFixed(2)),
            exitReason,
            points,
            lots: spec.recommendedLots,
            pnlInr,
            maxRiskInr: activePos.maxRiskInr,
            rrRatio: activePos.rrRatio,
          });

          activePos = null;
          lastExitIndex = i;
        }
      }

      // 2. Evaluate entry if flat
      if (
        !activePos &&
        isSession &&
        mins < 23 * 60 + 10 &&
        i - lastExitIndex >= 3
      ) {
        // Feed historical slice up to candle i
        const windowCandles = candles.slice(0, i + 1);
        const signal = McxAntiGravityScalperEngine.evaluateScalp({
          symbol: sym,
          candles: windowCandles,
        });

        if (signal.approved && signal.action !== 'WAIT') {
          activePos = {
            action: signal.action,
            mode: signal.mode,
            patternTag: signal.patternTag,
            entryDate: dateStr,
            entryTime: timeStr,
            entryPrice: signal.entryPrice,
            slPrice: signal.slPrice,
            tp1Price: signal.tp1Price,
            tp2Price: signal.tp2RunnerPrice,
            maxRiskInr: signal.maxRiskInr,
            rrRatio: signal.rrRatio,
            tp1Hit: false,
          };
        }
      }
    }
  }

  // Sort trades chronologically
  allTrades.sort((a, b) => (a.date + a.entryTime).localeCompare(b.date + b.entryTime));

  console.log(`Total Scalp Trades Executed: ${allTrades.length}`);
  console.log('\n' + '='.repeat(100));
  console.log(
    `${'Date'.padEnd(12)} | ${'Trades'.padEnd(7)} | ${'Wins'.padEnd(5)} | ${'Losses'.padEnd(7)} | ${'WinRate'.padEnd(8)} | ${'Gross Win (₹)'.padStart(15)} | ${'Gross Loss (₹)'.padStart(15)} | ${'Day Net P&L (₹)'.padStart(16)}`
  );
  console.log('='.repeat(100));

  const dateGroups: Record<string, BacktestTrade[]> = {};
  for (const t of allTrades) {
    if (!dateGroups[t.date]) dateGroups[t.date] = [];
    dateGroups[t.date].push(t);
  }

  let totalGrossWin = 0;
  let totalGrossLoss = 0;
  let totalNetPnl = 0;
  let totalWins = 0;

  for (const [d, trades] of Object.entries(dateGroups)) {
    const wins = trades.filter((t) => t.pnlInr > 0);
    const losses = trades.filter((t) => t.pnlInr < 0);
    const gw = wins.reduce((s, t) => s + t.pnlInr, 0);
    const gl = losses.reduce((s, t) => s + t.pnlInr, 0);
    const net = gw + gl;
    const wr = trades.length > 0 ? (wins.length / trades.length) * 100 : 0;

    totalGrossWin += gw;
    totalGrossLoss += gl;
    totalNetPnl += net;
    totalWins += wins.length;

    console.log(
      `${d.padEnd(12)} | ${String(trades.length).padEnd(7)} | ${String(wins.length).padEnd(5)} | ${String(losses.length).padEnd(7)} | ${wr.toFixed(1).padStart(6)}% | ${('+' + gw.toLocaleString('en-IN', { minimumFractionDigits: 2 })).padStart(15)} | ${gl.toLocaleString('en-IN', { minimumFractionDigits: 2 }).padStart(15)} | ${((net >= 0 ? '+' : '') + net.toLocaleString('en-IN', { minimumFractionDigits: 2 })).padStart(16)}`
    );
  }

  const daysCount = Object.keys(dateGroups).length || 1;
  const overallWr = allTrades.length > 0 ? (totalWins / allTrades.length) * 100 : 0;

  console.log('='.repeat(100));
  console.log(`TOTAL SESSIONS AUDITED:    ${daysCount} trading days`);
  console.log(`TOTAL REAL NET PROFIT:     ₹${(totalNetPnl >= 0 ? '+' : '') + totalNetPnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })} INR`);
  console.log(`AVERAGE PROFIT PER DAY:    ₹${(totalNetPnl / daysCount >= 0 ? '+' : '') + (totalNetPnl / daysCount).toLocaleString('en-IN', { minimumFractionDigits: 2 })} INR / day`);
  console.log(`OVERALL WIN RATE:          ${overallWr.toFixed(1)}%`);
  console.log(`AVERAGE TRADES PER DAY:    ${(allTrades.length / daysCount).toFixed(1)} trades / day`);
  console.log('='.repeat(100));

  console.log('\n📦 COMMODITY BREAKDOWN:');
  const symGroups: Record<string, BacktestTrade[]> = {};
  for (const t of allTrades) {
    if (!symGroups[t.symbol]) symGroups[t.symbol] = [];
    symGroups[t.symbol].push(t);
  }

  for (const [sym, trades] of Object.entries(symGroups)) {
    const wins = trades.filter((t) => t.pnlInr > 0);
    const net = trades.reduce((s, t) => s + t.pnlInr, 0);
    const wr = (wins.length / trades.length) * 100;
    console.log(
      `  • ${sym.padEnd(12)}: ${trades.length} trades | ${wins.length} wins (${wr.toFixed(1)}%) | Net P&L: ₹${(net >= 0 ? '+' : '') + net.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
    );
  }
}

runBacktest().catch(console.error);
