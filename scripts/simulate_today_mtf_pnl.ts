/**
 * scripts/simulate_today_mtf_pnl.ts
 * Real-market bar-by-bar simulation of today (16-Nov-2026) using
 * Mtf15mSupportResistanceOptionEngine + FoOptionSniperEngine logic.
 */

import fs from 'fs';
import {
  Mtf15mSupportResistanceOptionEngine,
  type Candle
} from '../lib/bharat/mtf15mSupportResistanceOptionEngine.ts';
import { FoOptionSniperEngine } from '../lib/bharat/foOptionSniperEngine.ts';
import { aggregate5mTo15m } from '../server.ts';

interface SimPosition {
  symbol: string;
  optionSymbol: string;
  optionType: 'CE' | 'PE';
  strike: number;
  lotSize: number;
  entrySpot: number;
  entryPremium: number;
  currentSlPremium: number;
  ladderStage: number;
  lockedProfitInr: number;
  peakProfitInr: number;
  entryTime: string;
  entryBarIdx: number;
  patternTag: string;
}

interface CompletedTrade {
  symbol: string;
  optionSymbol: string;
  optionType: 'CE' | 'PE';
  strike: number;
  lotSize: number;
  entryTime: string;
  exitTime: string;
  entryPremium: number;
  exitPremium: number;
  grossPnlInr: number;
  frictionInr: number;
  netPnlInr: number;
  ladderStage: number;
  exitReason: string;
  patternTag: string;
}

const LOT_CONFIGS: Record<string, { lotSize: number; strikeStep: number }> = {
  NIFTY: { lotSize: 75, strikeStep: 50 },
  BANKNIFTY: { lotSize: 30, strikeStep: 100 },
  ...FoOptionSniperEngine.FO_WHITELIST_50,
};

function formatIstTime(ts: number): string {
  const d = new Date(ts);
  // IST offset is UTC+5:30
  const utc = d.getTime() + d.getTimezoneOffset() * 60000;
  const ist = new Date(utc + 5.5 * 3600000);
  const hh = String(ist.getHours()).padStart(2, '0');
  const mm = String(ist.getMinutes()).padStart(2, '0');
  return `${hh}:${mm}`;
}

async function runSimulation() {
  const raw = fs.readFileSync('scripts/today_candles_5m.json', 'utf-8');
  const allData: Record<string, Candle[]> = JSON.parse(raw);

  const symbols = Object.keys(allData);
  console.log(`Loaded ${symbols.length} instruments for simulation.`);

  const completedTrades: CompletedTrade[] = [];
  const openPositions: Map<string, SimPosition> = new Map();
  const lastExitBarIdx: Map<string, number> = new Map();

  // Index 300 to 374 corresponds to today's 75 bars (09:15 to 15:25 IST)
  // Let's find today's start index for NIFTY
  const niftyCandles = allData['NIFTY'];
  let todayStartIdx = -1;
  for (let i = 0; i < niftyCandles.length; i++) {
    const timeStr = formatIstTime(niftyCandles[i].timestamp);
    if (timeStr === '09:15') {
      // Find the last 09:15 bar (today)
      todayStartIdx = i;
    }
  }

  console.log(`Today starts at index ${todayStartIdx} (${formatIstTime(niftyCandles[todayStartIdx].timestamp)} IST)`);
  const todayEndIdx = niftyCandles.length - 1;

  // Simulate bar by bar through today
  for (let barIdx = todayStartIdx + 6; barIdx <= todayEndIdx; barIdx++) {
    const currentTs = niftyCandles[barIdx].timestamp;
    const timeStr = formatIstTime(currentTs);
    const isEodSquareOff = timeStr >= '15:15';

    // 1. UPDATE AND EVALUATE EXISTING OPEN POSITIONS FIRST
    for (const [sym, pos] of Array.from(openPositions.entries())) {
      const symCandles = allData[sym];
      if (!symCandles || !symCandles[barIdx]) continue;
      const bar = symCandles[barIdx];

      const delta = 0.55;
      const spotChange = pos.optionType === 'CE' ? bar.close - pos.entrySpot : pos.entrySpot - bar.close;
      const highSpotChange = pos.optionType === 'CE' ? bar.high - pos.entrySpot : pos.entrySpot - bar.low;
      const lowSpotChange = pos.optionType === 'CE' ? bar.low - pos.entrySpot : pos.entrySpot - bar.high;

      const currentPrem = Math.max(0.1, Number((pos.entryPremium + spotChange * delta).toFixed(2)));
      const highPrem = Math.max(0.1, Number((pos.entryPremium + highSpotChange * delta).toFixed(2)));
      const lowPrem = Math.max(0.1, Number((pos.entryPremium + lowSpotChange * delta).toFixed(2)));

      const maxFloatingPnl = (highPrem - pos.entryPremium) * pos.lotSize;
      if (maxFloatingPnl > pos.peakProfitInr) {
        pos.peakProfitInr = maxFloatingPnl;
      }

      // Infinite Progressive Profit Ladder (steps of ₹500)
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

      // Hard SL check (-₹2,500) intra-candle
      if (lowPrem <= pos.entryPremium - 2500 / pos.lotSize) {
        exitNow = true;
        exitPrice = Number((pos.entryPremium - 2500 / pos.lotSize).toFixed(2));
        exitReason = 'HARD_SL_2500_HIT';
      }
      // Trailing SL check on candle close for breathing room
      else if (pos.ladderStage > 0 && currentPrem <= pos.currentSlPremium) {
        exitNow = true;
        exitPrice = pos.currentSlPremium;
        exitReason = `TP${pos.ladderStage}_TRAIL_HIT`;
      } else if (isEodSquareOff) {
        exitNow = true;
        exitPrice = currentPrem;
        exitReason = 'AUTO_SQUARE_OFF_318PM';
      }

      if (exitNow) {
        const grossPnl = Number(((exitPrice - pos.entryPremium) * pos.lotSize).toFixed(2));
        const friction = 62.0; // Brokerage + STT + Turnover fees
        const netPnl = Number((grossPnl - friction).toFixed(2));

        completedTrades.push({
          symbol: pos.symbol,
          optionSymbol: pos.optionSymbol,
          optionType: pos.optionType,
          strike: pos.strike,
          lotSize: pos.lotSize,
          entryTime: pos.entryTime,
          exitTime: timeStr,
          entryPremium: pos.entryPremium,
          exitPremium: exitPrice,
          grossPnlInr: grossPnl,
          frictionInr: friction,
          netPnlInr: netPnl,
          ladderStage: pos.ladderStage,
          exitReason,
          patternTag: pos.patternTag,
        });

        lastExitBarIdx.set(sym, barIdx);
        openPositions.delete(sym);
      }
    }

    // 2. DO NOT ENTER NEW TRADES AFTER 15:00 PM IST
    if (timeStr >= '15:00') continue;

    // 3. SCAN FOR NEW MTF 15M S&R ENTRIES
    for (const sym of symbols) {
      if (openPositions.has(sym)) continue; // Max 1 trade per symbol
      if (lastExitBarIdx.has(sym) && barIdx - lastExitBarIdx.get(sym)! < 3) continue; // 15-min cooldown
      const cfg = LOT_CONFIGS[sym];
      if (!cfg) continue;

      const sym5m = allData[sym];
      if (!sym5m || sym5m.length <= barIdx) continue;

      const window5m = sym5m.slice(0, barIdx + 1);
      const window15m = aggregate5mTo15m(window5m);

      if (window5m.length < 45 || window15m.length < 25) continue;

      const decision = Mtf15mSupportResistanceOptionEngine.evaluateSetup({
        symbol: sym,
        candles15m: window15m,
        candles5m: window5m,
        lotSize: cfg.lotSize,
        strikeStep: cfg.strikeStep,
      });

      if (decision.approved && (decision.action === 'BUY_ATM_CE' || decision.action === 'BUY_ATM_PE')) {
        const currentSpot = sym5m[barIdx].close;
        const optType = decision.action === 'BUY_ATM_CE' ? 'CE' : 'PE';
        const strike = decision.atmStrike;
        const optSym = `${sym}26NOV${strike}${optType}`;

        const entryPrem = Number((currentSpot * 0.022).toFixed(2));
        // Hard SL: -₹2,500 max loss per lot
        const slPoints = Number((2500 / cfg.lotSize).toFixed(2));
        const initialSlPrem = Number((entryPrem - slPoints).toFixed(2));

        openPositions.set(sym, {
          symbol: sym,
          optionSymbol: optSym,
          optionType: optType,
          strike,
          lotSize: cfg.lotSize,
          entrySpot: currentSpot,
          entryPremium: entryPrem,
          currentSlPremium: initialSlPrem,
          ladderStage: 0,
          lockedProfitInr: 0,
          peakProfitInr: 0,
          entryTime: timeStr,
          entryBarIdx: barIdx,
          patternTag: decision.patternTag,
        });
      }
    }
  }

  console.log('\n' + '='.repeat(80));
  console.log('📊 REAL-MARKET BACKTEST RESULTS FOR TODAY (16-NOV-2026)');
  console.log('='.repeat(80));

  let totalGross = 0;
  let totalNet = 0;
  let wins = 0;
  let losses = 0;

  console.log('| Symbol | Option | Entry | Exit | Entry Pr | Exit Pr | Stage | Exit Reason | Net P&L (₹) |');
  console.log('| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |');

  for (const t of completedTrades) {
    totalGross += t.grossPnlInr;
    totalNet += t.netPnlInr;
    if (t.netPnlInr > 0) wins++;
    else losses++;

    console.log(
      `| **${t.symbol}** | ${t.optionSymbol} | ${t.entryTime} | ${t.exitTime} | ₹${t.entryPremium.toFixed(1)} | ₹${t.exitPremium.toFixed(1)} | Stage ${t.ladderStage} | ${t.exitReason} | **${t.netPnlInr >= 0 ? '+' : ''}₹${t.netPnlInr.toFixed(2)}** |`
    );
  }

  console.log('='.repeat(80));
  console.log(`Total Trades Executed: ${completedTrades.length}`);
  console.log(`Winning Trades:        ${wins} (${((wins / Math.max(1, completedTrades.length)) * 100).toFixed(1)}%)`);
  console.log(`Losing Trades:         ${losses}`);
  console.log(`Gross Realized P&L:    ₹${totalGross.toFixed(2)}`);
  console.log(`Total Statutory/Friction: ₹${(completedTrades.length * 62).toFixed(2)}`);
  console.log(`GRAND TOTAL NET PROFIT: ₹${totalNet.toFixed(2)}`);
  console.log('='.repeat(80));
}

runSimulation().catch((err) => {
  console.error('Simulation error:', err);
});
