/**
 * scripts/simulate_cash_equity_today.ts
 * ============================================================================
 * CASH EQUITY (INTRADAY MIS / 5X LEVERAGE) VS OPTIONS COMPARISON FOR 18-NOV-2026
 * 
 * Compares:
 *   1. No Options (Pure Cash Equity Intraday Long / Short):
 *      - No theta/time decay
 *      - 1:1 price tracking (Delta = 1.0)
 *      - BUT: Full turnover statutory taxes (STT on full share value, turnover charges)
 *   2. Capital: ₹1,00,000 (with standard 5x MIS leverage = ₹5,00,000 total buying power)
 *      - 5 active seats = ₹1,00,000 exposure per stock trade (₹20,000 margin used)
 * ============================================================================
 */

import {
  Mtf15mSupportResistanceOptionEngine,
  type Candle,
} from '../lib/bharat/mtf15mSupportResistanceOptionEngine.ts';
import { aggregate5mTo15m } from './audit_today_18nov_real_market.ts';

interface StockConfig {
  symbol: string;
  ticker: string;
  lotSize: number;
  strikeStep: number;
}

const STOCKS: StockConfig[] = [
  { symbol: 'RELIANCE', ticker: 'RELIANCE.NS', lotSize: 500, strikeStep: 10 },
  { symbol: 'HDFCBANK', ticker: 'HDFCBANK.NS', lotSize: 550, strikeStep: 10 },
  { symbol: 'ICICIBANK', ticker: 'ICICIBANK.NS', lotSize: 700, strikeStep: 10 },
  { symbol: 'AXISBANK', ticker: 'AXISBANK.NS', lotSize: 625, strikeStep: 10 },
  { symbol: 'SBIN', ticker: 'SBIN.NS', lotSize: 750, strikeStep: 10 },
  { symbol: 'KOTAKBANK', ticker: 'KOTAKBANK.NS', lotSize: 2000, strikeStep: 5 },
  { symbol: 'TCS', ticker: 'TCS.NS', lotSize: 225, strikeStep: 20 },
  { symbol: 'INFY', ticker: 'INFY.NS', lotSize: 400, strikeStep: 14 },
  { symbol: 'LT', ticker: 'LT.NS', lotSize: 175, strikeStep: 20 },
  { symbol: 'TATASTEEL', ticker: 'TATASTEEL.NS', lotSize: 2750, strikeStep: 2.5 },
  { symbol: 'BAJFINANCE', ticker: 'BAJFINANCE.NS', lotSize: 750, strikeStep: 10 },
];

async function fetchCandles(ticker: string): Promise<Candle[]> {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${ticker}?range=5d&interval=5m`;
  const res = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' } });
  if (!res.ok) return [];
  const data = (await res.json()) as any;
  const result = data?.chart?.result?.[0];
  if (!result) return [];
  const q = result.indicators?.quote?.[0];
  const ts = result.timestamp;
  if (!q || !ts) return [];

  const candles: Candle[] = [];
  for (let i = 0; i < ts.length; i++) {
    if (q.open[i] == null || q.close[i] == null) continue;
    candles.push({
      timestamp: ts[i] * 1000,
      open: q.open[i],
      high: q.high[i],
      low: q.low[i],
      close: q.close[i],
      volume: q.volume[i] || 1000,
    });
  }
  return candles;
}

function getIstTimeStr(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString('en-GB', { timeZone: 'Asia/Kolkata', hour12: false });
}

function getIstDateStr(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });
}

// Statutory charges in India for Intraday Cash Equity (MIS)
function calculateCashFriction(entryPrice: number, exitPrice: number, qty: number): number {
  const buyVal = entryPrice * qty;
  const sellVal = exitPrice * qty;
  const totalTurnover = buyVal + sellVal;

  const brokerage = 40; // ₹20 buy + ₹20 sell
  const stt = sellVal * 0.00025; // 0.025% on sell turnover
  const exchangeCharges = totalTurnover * 0.0000345; // NSE 0.00345%
  const sebiCharges = totalTurnover * 0.000001; // ₹10 per crore
  const stampDuty = buyVal * 0.00003; // 0.003% on buy
  const gst = (brokerage + exchangeCharges + sebiCharges) * 0.18;

  return Number((brokerage + stt + exchangeCharges + sebiCharges + stampDuty + gst).toFixed(2));
}

interface CashPosition {
  id: string;
  symbol: string;
  side: 'BUY' | 'SHORT';
  shares: number;
  entryPrice: number;
  currentPrice: number;
  peakPnl: number;
  entryTime: string;
  entryBarIdx: number;
  slPrice: number;
  softLockInr: number;
}

interface CompletedCashTrade {
  time: string;
  symbol: string;
  side: 'BUY' | 'SHORT';
  shares: number;
  entryPrice: number;
  exitPrice: number;
  exitTime: string;
  exitReason: string;
  grossPnl: number;
  friction: number;
  netPnl: number;
}

async function runCashSimulation() {
  console.log('================================================================================');
  console.log('📊 SIMULATION: "AGAR NORMAL MEIN (BINA OPTION KE) CASH EQUITY ME TRADE KIYA HOTA"');
  console.log('   Capital: ₹1,00,000 | 5x MIS Intraday Leverage | 5-Seat Portfolio');
  console.log('   Exposure per stock: ₹1,00,000 (Margin used: ₹20,000 per position)');
  console.log('================================================================================\n');

  const candleMap = new Map<string, Candle[]>();
  const todayBarIndices = new Map<string, number[]>();

  for (const item of STOCKS) {
    const candles = await fetchCandles(item.ticker);
    candleMap.set(item.symbol, candles);

    const todayIdxs: number[] = [];
    for (let i = 0; i < candles.length; i++) {
      const c = candles[i];
      const dateStr = getIstDateStr(c.timestamp);
      const timeStr = getIstTimeStr(c.timestamp);
      if (dateStr === '2026-11-18' && timeStr >= '09:15:00' && timeStr <= '15:30:00') {
        todayIdxs.push(i);
      }
    }
    todayBarIndices.set(item.symbol, todayIdxs);
  }

  const completedTrades: CompletedCashTrade[] = [];
  const openPositions: CashPosition[] = [];
  const symbolCooldowns = new Map<string, number>();

  const masterCandles = candleMap.get('RELIANCE') || [];
  const masterIdxs = todayBarIndices.get('RELIANCE') || [];

  for (const mIdx of masterIdxs) {
    const currentMasterCandle = masterCandles[mIdx];
    const currentTimeStr = getIstTimeStr(currentMasterCandle.timestamp);
    const currentTs = currentMasterCandle.timestamp;

    // 1. UPDATE ACTIVE CASH POSITIONS
    for (let pIdx = openPositions.length - 1; pIdx >= 0; pIdx--) {
      const pos = openPositions[pIdx];
      const symCandles = candleMap.get(pos.symbol) || [];
      const curBar = symCandles.find((c) => Math.abs(c.timestamp - currentTs) < 150000);
      if (!curBar) continue;

      pos.currentPrice = curBar.close;
      const curPnl =
        pos.side === 'BUY'
          ? (pos.currentPrice - pos.entryPrice) * pos.shares
          : (pos.entryPrice - pos.currentPrice) * pos.shares;

      if (curPnl > pos.peakPnl) {
        pos.peakPnl = curPnl;
      }

      // Check Trailing & Stop Loss
      // Cash Stop Loss: Max -₹1,200 per position (since capital is ₹20k per seat, 6% stop)
      // Profit Lock: +₹500 -> Lock +₹300, +₹1000 -> Lock +₹700, +₹2000 -> Lock 80%
      if (pos.peakPnl >= 2000) {
        pos.softLockInr = Math.max(pos.softLockInr, pos.peakPnl * 0.80);
      } else if (pos.peakPnl >= 1000) {
        pos.softLockInr = Math.max(pos.softLockInr, 700);
      } else if (pos.peakPnl >= 500) {
        pos.softLockInr = Math.max(pos.softLockInr, 300);
      }

      let exitReason = '';
      if (curPnl <= -1200) {
        exitReason = 'CASH_SL_HIT (-₹1,200)';
      } else if (pos.softLockInr > 0 && curPnl <= pos.softLockInr) {
        exitReason = `CASH_PROFIT_TRAIL (+₹${pos.softLockInr.toFixed(0)})`;
      } else if (currentTimeStr >= '15:18:00') {
        exitReason = 'MANDATORY_INTRADAY_AUTO_SQUARE_OFF (03:18 PM)';
      }

      if (exitReason) {
        const exitPrice = pos.currentPrice;
        const grossPnl = Number(
          (pos.side === 'BUY' ? (exitPrice - pos.entryPrice) * pos.shares : (pos.entryPrice - exitPrice) * pos.shares).toFixed(2)
        );
        const friction = calculateCashFriction(pos.entryPrice, exitPrice, pos.shares);
        completedTrades.push({
          time: pos.entryTime,
          symbol: pos.symbol,
          side: pos.side,
          shares: pos.shares,
          entryPrice: pos.entryPrice,
          exitPrice,
          exitTime: currentTimeStr,
          exitReason,
          grossPnl,
          friction,
          netPnl: Number((grossPnl - friction).toFixed(2)),
        });
        openPositions.splice(pIdx, 1);
        symbolCooldowns.set(pos.symbol, currentTs + 30 * 60 * 1000);
      }
    }

    // 2. SCAN FOR NEW SIGNALS (Max 5 Seats)
    if (currentTimeStr > '15:15:00') continue;
    if (openPositions.length >= 5) continue;

    for (const item of STOCKS) {
      if (openPositions.length >= 5) break;
      if (openPositions.some((p) => p.symbol === item.symbol)) continue;

      const cooldown = symbolCooldowns.get(item.symbol) || 0;
      if (currentTs < cooldown) continue;

      const symCandles = candleMap.get(item.symbol) || [];
      const barIdx = symCandles.findIndex((c) => Math.abs(c.timestamp - currentTs) < 150000);
      if (barIdx < 45) continue;

      const history5m = symCandles.slice(0, barIdx + 1);
      const history15m = aggregate5mTo15m(history5m);
      if (history15m.length < 25) continue;

      const decision = Mtf15mSupportResistanceOptionEngine.evaluateSetup({
        symbol: item.symbol,
        candles15m: history15m,
        candles5m: history5m,
        lotSize: item.lotSize,
        strikeStep: item.strikeStep,
      });

      if (!decision.approved || decision.action === 'WAIT') continue;

      const side: 'BUY' | 'SHORT' = decision.action === 'BUY_ATM_CE' ? 'BUY' : 'SHORT';
      const spotPrice = decision.underlyingSpot;

      // Position Sizing: ₹1,00,000 exposure per trade (₹20,000 margin at 5x MIS leverage)
      const targetExposure = 100000;
      const shares = Math.max(1, Math.floor(targetExposure / spotPrice));

      openPositions.push({
        id: `${item.symbol}-${side}-${currentTs}`,
        symbol: item.symbol,
        side,
        shares,
        entryPrice: spotPrice,
        currentPrice: spotPrice,
        peakPnl: 0,
        entryTime: currentTimeStr,
        entryBarIdx: barIdx,
        slPrice: side === 'BUY' ? spotPrice * 0.988 : spotPrice * 1.012, // 1.2% hard stop
        softLockInr: 0,
      });
    }
  }

  // Square off remaining at 03:18 PM
  for (const pos of openPositions) {
    const grossPnl = Number(
      (pos.side === 'BUY' ? (pos.currentPrice - pos.entryPrice) * pos.shares : (pos.entryPrice - pos.currentPrice) * pos.shares).toFixed(2)
    );
    const friction = calculateCashFriction(pos.entryPrice, pos.currentPrice, pos.shares);
    completedTrades.push({
      time: pos.entryTime,
      symbol: pos.symbol,
      side: pos.side,
      shares: pos.shares,
      entryPrice: pos.entryPrice,
      exitPrice: pos.currentPrice,
      exitTime: '15:18:00',
      exitReason: 'MANDATORY_INTRADAY_AUTO_SQUARE_OFF (03:18 PM)',
      grossPnl,
      friction,
      netPnl: Number((grossPnl - friction).toFixed(2)),
    });
  }

  // Print Comparison Results
  console.log(
    '#'.padEnd(4) +
    'Time'.padEnd(10) +
    'Symbol'.padEnd(12) +
    'Side'.padEnd(8) +
    'Shares'.padEnd(10) +
    'Entry (₹)'.padEnd(12) +
    'Exit (₹)'.padEnd(12) +
    'Gross P&L'.padEnd(14) +
    'Taxes (₹)'.padEnd(12) +
    'Net P&L (₹)'.padEnd(14) +
    'Exit Reason'
  );
  console.log('-'.repeat(125));

  let totalGross = 0;
  let totalTaxes = 0;
  let wins = 0;
  let losses = 0;

  completedTrades.forEach((t, idx) => {
    totalGross += t.grossPnl;
    totalTaxes += t.friction;
    if (t.netPnl > 0) wins++;
    else losses++;

    const sign = t.netPnl >= 0 ? '+' : '';
    console.log(
      String(idx + 1).padEnd(4) +
      t.time.padEnd(10) +
      t.symbol.padEnd(12) +
      t.side.padEnd(8) +
      String(t.shares).padEnd(10) +
      `₹${t.entryPrice.toFixed(1)}`.padEnd(12) +
      `₹${t.exitPrice.toFixed(1)}`.padEnd(12) +
      `${t.grossPnl >= 0 ? '+' : ''}₹${t.grossPnl.toFixed(0)}`.padEnd(14) +
      `-₹${t.friction.toFixed(0)}`.padEnd(12) +
      `${sign}₹${t.netPnl.toFixed(0)}`.padEnd(14) +
      t.exitReason
    );
  });
  console.log('-'.repeat(125));

  const totalNet = totalGross - totalTaxes;
  console.log('\n================================================================================');
  console.log('📌 FINAL CASH EQUITY (BINA OPTION) SUMMARY ON ₹1,00,000 CAPITAL');
  console.log('================================================================================');
  console.log(`Starting Capital     : ₹1,00,000`);
  console.log(`Total Trades Taken   : ${completedTrades.length}`);
  console.log(`Winning Trades       : ${wins} (${((wins / completedTrades.length) * 100).toFixed(1)}% Win Rate)`);
  console.log(`Losing Trades        : ${losses}`);
  console.log(`Gross Realized P&L   : ${totalGross >= 0 ? '+' : ''}₹${totalGross.toFixed(2)}`);
  console.log(`Statutory Turnover Taxes & STT : -₹${totalTaxes.toFixed(2)} (High STT & turnover charges on full stock price!)`);
  console.log(`True Net Day P&L     : ${totalNet >= 0 ? '+' : ''}₹${totalNet.toFixed(2)}`);
  console.log(`Ending Account Equity: ₹${(100000 + totalNet).toFixed(2)} (${((totalNet / 100000) * 100).toFixed(2)}% Return)`);
  console.log('================================================================================\n');
}

runCashSimulation().catch(console.error);
