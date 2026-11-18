/**
 * scripts/simulate_mcx_exact_today.ts
 * Real-market bar-by-bar simulation of today (16-Nov-2026) for MCX Commodities:
 * CRUDEOIL, NATURALGAS, GOLD, SILVER, COPPER
 * Rules:
 *   - 09:00 AM to 11:20 PM IST
 *   - 15m S&R Macro Pivot Confluence
 *   - Pure Option Buying (BUY ATM CE / BUY ATM PE)
 *   - Hard SL: Strictly -₹2,500 per lot max risk
 *   - Trailing Ladder: TP1 (+500 -> Lock +150), TP2 (+1000 -> Lock +600), +2000 (Lock +1400), +4000 (Lock +3000), +8000 Runner (Lock +6500 & trail 1000 behind peak)
 *   - Mandatory Auto Square-Off at 11:20 PM IST
 */

import fs from 'fs';
import {
  McxCommodityOptionSniperEngine,
  type McxCandle
} from '../lib/mcx/mcxCommodityOptionSniperEngine.ts';
import { aggregateMcx5mTo15m } from '../mcxServer.ts';

interface McxTradeLog {
  symbol: string;
  optionSymbol: string;
  type: 'CE' | 'PE';
  strike: number;
  lotSize: number;
  entryTime: string;
  exitTime: string;
  entrySpot: number;
  exitSpot: number;
  entryPremium: number;
  exitPremium: number;
  grossPnl: number;
  friction: number;
  netPnl: number;
  stageReached: number;
  exitReason: string;
  patternTag: string;
}

function formatIst(ts: number): string {
  const d = new Date(ts);
  const utc = d.getTime() + d.getTimezoneOffset() * 60000;
  const ist = new Date(utc + 5.5 * 3600000);
  const hh = String(ist.getHours()).padStart(2, '0');
  const mm = String(ist.getMinutes()).padStart(2, '0');
  return `${hh}:${mm}`;
}

async function runMcxSim() {
  const res = await fetch('http://127.0.0.1:8000/api/mcx/candles-batch');
  const allData = (await res.json()) as Record<string, McxCandle[]>;

  const trades: McxTradeLog[] = [];
  const openPositions: Map<
    string,
    {
      symbol: string;
      optionSymbol: string;
      type: 'CE' | 'PE';
      strike: number;
      lotSize: number;
      entrySpot: number;
      entryPremium: number;
      currentSlPremium: number;
      ladderStage: number;
      lockedProfitInr: number;
      peakProfitInr: number;
      entryTime: string;
      patternTag: string;
    }
  > = new Map();
  const lastExitBarIdx: Map<string, number> = new Map();

  const commodities = ['CRUDEOIL', 'SILVER', 'NATURALGAS', 'GOLD', 'COPPER'];
  const crudeBars = allData['CRUDEOIL'];

  // Find today's bars (between 09:00 AM and 23:20 PM on 2026-11-16)
  const todayIndices: number[] = [];
  for (let i = 0; i < crudeBars.length; i++) {
    const t = formatIst(crudeBars[i].timestamp);
    const d = new Date(crudeBars[i].timestamp + 5.5 * 3600000);
    if (d.getUTCDate() === 16 && t >= '09:00' && t <= '23:25') {
      todayIndices.push(i);
    }
  }

  console.log(`Simulating ${todayIndices.length} 5m bars for MCX today (${formatIst(crudeBars[todayIndices[0]].timestamp)} to ${formatIst(crudeBars[todayIndices[todayIndices.length - 1]].timestamp)} IST)`);

  for (const barIdx of todayIndices) {
    const currentTs = crudeBars[barIdx].timestamp;
    const timeStr = formatIst(currentTs);
    const isEodSquareOff = timeStr >= '23:20';

    // 1. UPDATE AND EVALUATE OPEN POSITIONS
    for (const [sym, pos] of Array.from(openPositions.entries())) {
      const symCandles = allData[sym];
      if (!symCandles || !symCandles[barIdx]) continue;
      const bar = symCandles[barIdx];

      const delta = 0.55;
      const spotChange = pos.type === 'CE' ? bar.close - pos.entrySpot : pos.entrySpot - bar.close;
      const highSpotChange = pos.type === 'CE' ? bar.high - pos.entrySpot : pos.entrySpot - bar.low;
      const lowSpotChange = pos.type === 'CE' ? bar.low - pos.entrySpot : pos.entrySpot - bar.high;

      const currentPrem = Math.max(0.1, Number((pos.entryPremium + spotChange * delta).toFixed(2)));
      const highPrem = Math.max(0.1, Number((pos.entryPremium + highSpotChange * delta).toFixed(2)));
      const lowPrem = Math.max(0.1, Number((pos.entryPremium + lowSpotChange * delta).toFixed(2)));

      const maxFloatingPnl = (highPrem - pos.entryPremium) * pos.lotSize;
      if (maxFloatingPnl > pos.peakProfitInr) {
        pos.peakProfitInr = maxFloatingPnl;
      }

      // Check Infinite Progressive Trailing Profit Ladder (TP1: +₹500, TP2: +₹1,000 ... Infinite)
      if (pos.peakProfitInr >= 500) {
        const step = Math.floor(pos.peakProfitInr / 500);
        const stepLocked = step === 1 ? 150 : 150 + (step - 1) * 450;
        const dynamicTrail =
          pos.peakProfitInr >= 4000
            ? Math.max(stepLocked, pos.peakProfitInr - 1000)
            : stepLocked;
        const newLock = Math.max(pos.lockedProfitInr, dynamicTrail);

        if (newLock > pos.lockedProfitInr) {
          pos.lockedProfitInr = newLock;
          pos.ladderStage = Math.max(pos.ladderStage, step);
          pos.currentSlPremium = Number((pos.entryPremium + newLock / pos.lotSize).toFixed(2));
        }
      }

      // Check Exits:
      let exitNow = false;
      let exitPrice = currentPrem;
      let exitReason = '';

      // Hard SL check intra-candle (lowPrem)
      if (lowPrem <= pos.entryPremium - 2500 / pos.lotSize) {
        exitNow = true;
        exitPrice = Number((pos.entryPremium - 2500 / pos.lotSize).toFixed(2));
        exitReason = 'HARD_SL_2500_HIT';
      }
      // Trailing SL check on candle close to give full breathing room against noise wicks
      else if (pos.ladderStage > 0 && currentPrem <= pos.currentSlPremium) {
        exitNow = true;
        exitPrice = pos.currentSlPremium;
        exitReason = `TP${pos.ladderStage}_TRAIL_HIT`;
      } else if (isEodSquareOff) {
        exitNow = true;
        exitPrice = currentPrem;
        exitReason = 'MCX_AUTO_SQUARE_OFF_1120PM';
      }

      if (exitNow) {
        const grossPnl = Number(((exitPrice - pos.entryPremium) * pos.lotSize).toFixed(2));
        const friction = 62.0; // Brokerage + STT
        const netPnl = Number((grossPnl - friction).toFixed(2));

        trades.push({
          symbol: pos.symbol,
          optionSymbol: pos.optionSymbol,
          type: pos.type,
          strike: pos.strike,
          lotSize: pos.lotSize,
          entryTime: pos.entryTime,
          exitTime: timeStr,
          entrySpot: pos.entrySpot,
          exitSpot: bar.close,
          entryPremium: pos.entryPremium,
          exitPremium: exitPrice,
          grossPnl,
          friction,
          netPnl,
          stageReached: pos.ladderStage,
          exitReason,
          patternTag: pos.patternTag,
        });

        lastExitBarIdx.set(sym, barIdx);
        openPositions.delete(sym);
      }
    }

    if (timeStr < '09:30' || timeStr >= '23:00') continue; // Trade strictly between 09:30 AM and 11:00 PM IST

    // 2. SCAN FOR NEW 15M S&R ENTRIES
    for (const sym of commodities) {
      if (openPositions.has(sym)) continue;
      if (lastExitBarIdx.has(sym) && barIdx - lastExitBarIdx.get(sym)! < 3) continue; // 15-min cooldown
      const cfg = McxCommodityOptionSniperEngine.MCX_WHITELIST[sym];
      const symBars = allData[sym];
      if (!symBars || symBars.length <= barIdx) continue;

      const w5m = symBars.slice(0, barIdx + 1);
      const w15m = aggregateMcx5mTo15m(w5m);

      if (w5m.length < 40 || w15m.length < 24) continue;

      const decision = McxCommodityOptionSniperEngine.evaluateSetup({
        commoditySymbol: sym,
        candles15m: w15m,
        candles5m: w5m,
      });

      if (decision.approved && (decision.action === 'BUY_ATM_CE' || decision.action === 'BUY_ATM_PE')) {
        const spot = symBars[barIdx].close;
        const optType = decision.action === 'BUY_ATM_CE' ? 'CE' : 'PE';
        const strike = decision.atmStrike;
        const optSym = `${sym}26NOV${strike}${optType}`;

        const entryPrem = Number((spot * 0.02).toFixed(2)); // ~2% ATM premium
        const maxDrop = 2500 / cfg.lotSize;
        const initialSl = Number((entryPrem - maxDrop).toFixed(2));

        openPositions.set(sym, {
          symbol: sym,
          optionSymbol: optSym,
          type: optType,
          strike,
          lotSize: cfg.lotSize,
          entrySpot: spot,
          entryPremium: entryPrem,
          currentSlPremium: initialSl,
          ladderStage: 0,
          lockedProfitInr: 0,
          peakProfitInr: 0,
          entryTime: timeStr,
          patternTag: decision.patternTag,
        });
      }
    }
  }

  console.log('\n================================================================================');
  console.log('🛢️ MCX COMMODITY REAL-MARKET BACKTEST FOR TODAY (16-NOV-2026)');
  console.log('================================================================================');

  let totalGross = 0;
  let totalNet = 0;
  let wins = 0;
  let losses = 0;

  console.log('| Commodity | Option Symbol | Side | Entry | Exit | Entry Pr | Exit Pr | Stage | Exit Reason | Net P&L (₹) |');
  console.log('| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |');

  for (const t of trades) {
    totalGross += t.grossPnl;
    totalNet += t.netPnl;
    if (t.netPnl > 0) wins++;
    else losses++;
    console.log(
      `| **${t.symbol}** | ${t.optionSymbol} | **BUY ${t.type}** | ${t.entryTime} | ${t.exitTime} | ₹${t.entryPremium.toFixed(1)} | ₹${t.exitPremium.toFixed(1)} | Stage ${t.stageReached} | ${t.exitReason} | **${t.netPnl >= 0 ? '+' : ''}₹${t.netPnl.toFixed(2)}** |`
    );
  }

  console.log('================================================================================');
  console.log(`Total MCX Trades:       ${trades.length}`);
  console.log(`Winning Trades:         ${wins} (${((wins / Math.max(1, trades.length)) * 100).toFixed(1)}%)`);
  console.log(`Losing Trades:          ${losses}`);
  console.log(`Gross Realized P&L:     ₹${totalGross.toFixed(2)}`);
  console.log(`Total Friction (₹62/tr): ₹${(trades.length * 62).toFixed(2)}`);
  console.log(`GRAND TOTAL NET PROFIT: +₹${totalNet.toFixed(2)}`);
  console.log('================================================================================\n');
}

runMcxSim().catch(err => {
  console.error('MCX sim error:', err);
});
