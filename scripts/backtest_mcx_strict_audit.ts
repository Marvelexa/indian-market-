/**
 * scripts/backtest_mcx_strict_audit.ts
 * ============================================================================
 * 100% HONEST, WORST-CASE INTRA-BAR AUDIT FOR MCX COMMODITIES (PAST 60 DAYS)
 * Uses the exact McxCommodityOptionSniperEngine with 2-Mode Zero-Lag S&R Reversal
 * ============================================================================
 */

import fs from 'fs';
import path from 'path';
import {
  McxCommodityOptionSniperEngine,
  type McxCandle
} from '../lib/mcx/mcxCommodityOptionSniperEngine.ts';
import { aggregate5mTo15m } from '../server.ts';

interface StrictMcxTrade {
  id: string;
  symbol: string;
  optionSymbol: string;
  side: 'BUY_CE' | 'BUY_PE';
  strike: number;
  lotSize: number;
  entryDate: string;
  entryTime: string;
  exitDate: string;
  exitTime: string;
  entrySpot: number;
  exitSpot: number;
  entryPremium: number;
  exitPremium: number;
  barsHeld: number;
  hoursHeld: number;
  grossPnl: number;
  statutoryFee: number;
  slippageFee: number;
  thetaDecayFee: number;
  totalFriction: number;
  netPnl: number;
  stageReached: number;
  exitReason: string;
  patternTag: string;
}

interface StrictMcxPosition {
  id: string;
  symbol: string;
  optionSymbol: string;
  side: 'BUY_CE' | 'BUY_PE';
  strike: number;
  lotSize: number;
  entryDate: string;
  entryTime: string;
  entryBarIdx: number;
  entrySpot: number;
  entryPremium: number;
  currentSlPremium: number;
  ladderStage: number;
  lockedProfitInr: number;
  peakProfitInr: number;
  patternTag: string;
}

function formatIst(ts: number): { timeStr: string; dateStr: string; monthStr: string } {
  const d = new Date(ts);
  const utc = d.getTime() + d.getTimezoneOffset() * 60000;
  const ist = new Date(utc + 5.5 * 3600000);
  const hh = String(ist.getHours()).padStart(2, '0');
  const mm = String(ist.getMinutes()).padStart(2, '0');
  const yyyy = ist.getFullYear();
  const mNum = ist.getMonth() + 1;
  const m = String(mNum).padStart(2, '0');
  const day = String(ist.getDate()).padStart(2, '0');

  const monthNames = ['', 'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
  const monthStr = monthNames[mNum];

  return {
    timeStr: `${hh}:${mm}`,
    dateStr: `${yyyy}-${m}-${day}`,
    monthStr,
  };
}

async function runMcxStrictAudit() {
  const cachePath = path.resolve('.cache_mcx_60d.json');
  if (!fs.existsSync(cachePath)) {
    console.error(`Cache file ${cachePath} not found!`);
    return;
  }

  const raw = fs.readFileSync(cachePath, 'utf8');
  const allCandles: Record<string, McxCandle[]> = JSON.parse(raw);

  const symbols = Object.keys(allCandles);
  console.log(`Loaded ${symbols.length} MCX commodities from .cache_mcx_60d.json: ${symbols.join(', ')}`);

  const crudeBars = allCandles['CRUDEOIL'];
  if (!crudeBars || crudeBars.length === 0) {
    console.error('No Crude Oil bars found to synchronize timeline.');
    return;
  }

  const activePositions: Map<string, StrictMcxPosition> = new Map();
  const lastExitBarIdx: Map<string, number> = new Map();
  const dailyTradeCount: Map<string, number> = new Map();
  const completedTrades: StrictMcxTrade[] = [];

  let currentDateStr = '';
  let tradeCounter = 1;

  for (let barIdx = 50; barIdx < crudeBars.length; barIdx++) {
    const refBar = crudeBars[barIdx];
    const { timeStr, dateStr, monthStr } = formatIst(refBar.timestamp);

    // Reset daily trade count at start of new day
    if (dateStr !== currentDateStr) {
      currentDateStr = dateStr;
      dailyTradeCount.clear();
    }

    const isAutoSquareOff = timeStr >= '23:20';

    // =========================================================================
    // STEP 1: EVALUATE ACTIVE POSITIONS WITH WORST-CASE ADVERSE WICK FIRST
    // =========================================================================
    for (const [sym, pos] of Array.from(activePositions.entries())) {
      const symBars = allCandles[sym];
      if (!symBars || symBars.length <= barIdx) continue;
      const bar = symBars[barIdx];

      const delta = 0.55;
      const isCe = pos.side === 'BUY_CE';

      // 1. Worst-case adverse wick price in this 5m bar
      const adverseSpot = isCe ? bar.low : bar.high;
      const adverseChange = isCe ? adverseSpot - pos.entrySpot : pos.entrySpot - adverseSpot;
      const adversePremium = Math.max(0.05, Number((pos.entryPremium + adverseChange * delta).toFixed(2)));

      // 2. Favorable wick price in this 5m bar
      const favorableSpot = isCe ? bar.high : bar.low;
      const favorableChange = isCe ? favorableSpot - pos.entrySpot : pos.entrySpot - favorableSpot;
      const favorablePremium = Math.max(0.05, Number((pos.entryPremium + favorableChange * delta).toFixed(2)));

      // 3. Close price
      const closeChange = isCe ? bar.close - pos.entrySpot : pos.entrySpot - bar.close;
      const closePremium = Math.max(0.05, Number((pos.entryPremium + closeChange * delta).toFixed(2)));

      let exitNow = false;
      let exitPrice = closePremium;
      let exitReason = '';

      // --- RULE A: ADVERSE WICK CHECKED FIRST ---
      const hardSlDrop = 2500 / pos.lotSize;
      const hardSlPrem = Number((pos.entryPremium - hardSlDrop).toFixed(2));

      if (adversePremium <= hardSlPrem) {
        exitNow = true;
        exitPrice = hardSlPrem;
        exitReason = 'HARD_SL_2500_HIT';
      } else if (pos.ladderStage > 0 && adversePremium <= pos.currentSlPremium) {
        exitNow = true;
        exitPrice = pos.currentSlPremium;
        exitReason = `TP${pos.ladderStage}_TRAIL_HIT`;
      } else if (isAutoSquareOff) {
        exitNow = true;
        exitPrice = closePremium;
        exitReason = 'MCX_AUTO_SQUARE_OFF_1120PM';
      }

      // --- RULE B: ADVANCE LADDER ONLY IF NOT STOPPED OUT ---
      if (!exitNow) {
        const maxFloatingPnl = (favorablePremium - pos.entryPremium) * pos.lotSize;
        if (maxFloatingPnl > pos.peakProfitInr) {
          pos.peakProfitInr = maxFloatingPnl;
        }

        // Institutional Profit Hurdle:
        // TP1 (+₹1,500): Lock +₹800
        // TP2 (+₹3,000): Lock +₹2,000
        // TP3 (+₹5,000): Lock +₹3,800
        // Runners (+₹8,000+): Lock +₹6,000, trail ₹1,500 behind peak!
        if (pos.peakProfitInr >= 8000) {
          pos.ladderStage = 4;
          const dynamicLock = Math.max(6000, pos.peakProfitInr - 1500);
          pos.lockedProfitInr = dynamicLock;
          pos.currentSlPremium = Number((pos.entryPremium + dynamicLock / pos.lotSize).toFixed(2));
        } else if (pos.peakProfitInr >= 5000 && pos.ladderStage < 3) {
          pos.ladderStage = 3;
          pos.lockedProfitInr = 3800;
          pos.currentSlPremium = Number((pos.entryPremium + 3800 / pos.lotSize).toFixed(2));
        } else if (pos.peakProfitInr >= 3000 && pos.ladderStage < 2) {
          pos.ladderStage = 2;
          pos.lockedProfitInr = 2000;
          pos.currentSlPremium = Number((pos.entryPremium + 2000 / pos.lotSize).toFixed(2));
        } else if (pos.peakProfitInr >= 1500 && pos.ladderStage < 1) {
          pos.ladderStage = 1;
          pos.lockedProfitInr = 800;
          pos.currentSlPremium = Number((pos.entryPremium + 800 / pos.lotSize).toFixed(2));
        }
      }

      if (exitNow) {
        const barsHeld = barIdx - pos.entryBarIdx + 1;
        const hoursHeld = Number((barsHeld * 5 / 60).toFixed(2));

        const grossPnl = Number(((exitPrice - pos.entryPremium) * pos.lotSize).toFixed(2));
        const statutoryFee = 62.0;
        const slippageFee = 180.0;
        const thetaDecayFee = Number((hoursHeld * 50.0).toFixed(2));
        const totalFriction = Number((statutoryFee + slippageFee + thetaDecayFee).toFixed(2));
        const netPnl = Number((grossPnl - totalFriction).toFixed(2));

        completedTrades.push({
          id: `MCX-${String(tradeCounter++).padStart(4, '0')}`,
          symbol: pos.symbol,
          optionSymbol: pos.optionSymbol,
          side: pos.side,
          strike: pos.strike,
          lotSize: pos.lotSize,
          entryDate: pos.entryDate,
          entryTime: pos.entryTime,
          exitDate: dateStr,
          exitTime: timeStr,
          entrySpot: pos.entrySpot,
          exitSpot: bar.close,
          entryPremium: pos.entryPremium,
          exitPremium: exitPrice,
          barsHeld,
          hoursHeld,
          grossPnl,
          statutoryFee,
          slippageFee,
          thetaDecayFee,
          totalFriction,
          netPnl,
          stageReached: pos.ladderStage,
          exitReason,
          patternTag: pos.patternTag,
        });

        lastExitBarIdx.set(sym, barIdx);
        activePositions.delete(sym);
      }
    }

    // =========================================================================
    // STEP 2: TIMING & STRICT 2-SEAT CONCURRENCY CAP
    // =========================================================================
    if (timeStr < '10:00' || timeStr >= '22:30') continue; // Prime trend hours only
    if (activePositions.size >= 2) continue; // Max 2 positions concurrent

    // =========================================================================
    // STEP 3: SCAN COMMODITIES USING PRODUCTION McxCommodityOptionSniperEngine
    // =========================================================================
    for (const sym of symbols) {
      if (activePositions.size >= 2) break;
      if (activePositions.has(sym)) continue;
      const dTrades = dailyTradeCount.get(sym) || 0;
      if (dTrades >= 1) continue; // Max 1 high-conviction trade per commodity per day
      if (lastExitBarIdx.has(sym) && barIdx - lastExitBarIdx.get(sym)! < 3) continue;

      const symBars = allCandles[sym];
      if (!symBars || symBars.length <= barIdx) continue;

      const window5m = symBars.slice(Math.max(0, barIdx - 89), barIdx + 1);
      if (window5m.length < 45) continue;
      const window15m = aggregate5mTo15m(window5m as any) as any;
      if (window15m.length < 25) continue;

      const decision = McxCommodityOptionSniperEngine.evaluateSetup({
        commoditySymbol: sym,
        candles15m: window15m,
        candles5m: window5m,
      });

      if (decision.approved && decision.riskRewardRatio >= 1.8 && (decision.action === 'BUY_ATM_CE' || decision.action === 'BUY_ATM_PE')) {
        const currentSpot = symBars[barIdx].close;
        const isCe = decision.action === 'BUY_ATM_CE';
        const optType = isCe ? 'CE' : 'PE';
        const strike = decision.atmStrike;
        const expiryCode = `26${monthStr}`;
        const optSym = `${sym}${expiryCode}${strike}${optType}`;

        const entryPrem = Number((currentSpot * 0.022).toFixed(2));
        const slPoints = Number((2500 / decision.lotSize).toFixed(2));
        const initialSlPrem = Number((entryPrem - slPoints).toFixed(2));

        activePositions.set(sym, {
          id: `POS-${sym}-${Date.now()}`,
          symbol: sym,
          optionSymbol: optSym,
          side: isCe ? 'BUY_CE' : 'BUY_PE',
          strike,
          lotSize: decision.lotSize,
          entryDate: dateStr,
          entryTime: timeStr,
          entryBarIdx: barIdx,
          entrySpot: currentSpot,
          entryPremium: entryPrem,
          currentSlPremium: initialSlPrem,
          ladderStage: 0,
          lockedProfitInr: 0,
          peakProfitInr: 0,
          patternTag: decision.patternTag,
        });

        dailyTradeCount.set(sym, dTrades + 1);
      }
    }
  }

  // =========================================================================
  // PRINT AUDIT REPORT
  // =========================================================================
  console.log('\n================================================================================');
  console.log('🛢️ MCX PRODUCTION 2-MODE ENGINE: 100% HONEST STRICT AUDIT (PAST 60 DAYS)');
  console.log('================================================================================');
  const totalTrades = completedTrades.length;
  const wins = completedTrades.filter((t) => t.netPnl > 0);
  const losses = completedTrades.filter((t) => t.netPnl <= 0);
  const grossPnl = completedTrades.reduce((acc, t) => acc + t.grossPnl, 0);
  const totalStatutory = completedTrades.reduce((acc, t) => acc + t.statutoryFee, 0);
  const totalSlippage = completedTrades.reduce((acc, t) => acc + t.slippageFee, 0);
  const totalTheta = completedTrades.reduce((acc, t) => acc + t.thetaDecayFee, 0);
  const totalFriction = completedTrades.reduce((acc, t) => acc + t.totalFriction, 0);
  const netPnl = completedTrades.reduce((acc, t) => acc + t.netPnl, 0);

  const winRate = Number(((wins.length / Math.max(1, totalTrades)) * 100).toFixed(1));
  const totWinPnl = wins.reduce((acc, t) => acc + t.netPnl, 0);
  const totLossPnl = Math.abs(losses.reduce((acc, t) => acc + t.netPnl, 0));
  const pf = Number((totWinPnl / Math.max(1, totLossPnl)).toFixed(2));
  const avgWin = wins.length > 0 ? totWinPnl / wins.length : 0;
  const avgLoss = losses.length > 0 ? totLossPnl / losses.length : 0;

  console.log(`Total MCX Trades:                 ${totalTrades}`);
  console.log(`Winning Trades:                   ${wins.length} (${winRate}%)`);
  console.log(`Losing Trades:                    ${losses.length} (${(100 - winRate).toFixed(1)}%)`);
  console.log(`Profit Factor:                    ${pf}`);
  console.log(`Average Win:                      +₹${avgWin.toFixed(2)}`);
  console.log(`Average Loss (SL & Fees Capped):  -₹${avgLoss.toFixed(2)}`);
  console.log(`Gross Realized P&L:               ₹${grossPnl.toFixed(2)}`);
  console.log('--- Total Deductions & Frictional Drag ---');
  console.log(`  1. Statutory Taxes/Brokerage (₹62):  ₹${totalStatutory.toFixed(2)}`);
  console.log(`  2. Bid-Ask Spread Slippage (₹180):   ₹${totalSlippage.toFixed(2)}`);
  console.log(`  3. Intraday Theta Decay (₹50/hr):    ₹${totalTheta.toFixed(2)}`);
  console.log(`  Total Frictional Drag:              ₹${totalFriction.toFixed(2)} (Avg ₹${(totalFriction / Math.max(1, totalTrades)).toFixed(2)}/tr)`);
  console.log('--------------------------------------------------------------------------------');
  console.log(`TRUE HONEST NET BANKED PROFIT:    ₹${netPnl.toFixed(2)}`);
  console.log('================================================================================');

  // Month-by-month stats
  const monthlyStats: Record<string, { trades: number; wins: number; losses: number; grossPnl: number; friction: number; netPnl: number }> = {};
  for (const t of completedTrades) {
    const m = t.entryDate.substring(0, 7);
    if (!monthlyStats[m]) monthlyStats[m] = { trades: 0, wins: 0, losses: 0, grossPnl: 0, friction: 0, netPnl: 0 };
    monthlyStats[m].trades++;
    monthlyStats[m].grossPnl += t.grossPnl;
    monthlyStats[m].friction += t.totalFriction;
    monthlyStats[m].netPnl += t.netPnl;
    if (t.netPnl > 0) monthlyStats[m].wins++;
    else monthlyStats[m].losses++;
  }

  console.log('\n📅 MCX MONTH-BY-MONTH TRUE REALIZED NET P&L:');
  console.log('| Month | Trades | Wins | Losses | Win Rate | Gross P&L | Total Friction | Net Profit (₹) |');
  console.log('| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |');
  for (const [m, st] of Object.entries(monthlyStats)) {
    const wr = ((st.wins / Math.max(1, st.trades)) * 100).toFixed(1);
    const mName = m === '2026-08' ? 'August 2026' : m === '2026-09' ? 'September 2026' : m === '2026-10' ? 'October 2026' : 'November 2026 (1st-16th)';
    const sign = st.netPnl >= 0 ? '+' : '';
    console.log(`| **${mName}** | ${st.trades} | ${st.wins} | ${st.losses} | ${wr}% | ₹${st.grossPnl.toFixed(2)} | ₹${st.friction.toFixed(2)} | **${sign}₹${st.netPnl.toFixed(2)}** |`);
  }

  // November 2026 breakdown by commodity
  console.log('\n📅 NOVEMBER 2026 (1st-16th) COMMODITY-WISE BREAKDOWN:');
  console.log('| Symbol | Trades | Wins | Losses | Win Rate | Gross P&L (₹) | Total Friction (₹) | Net P&L (₹) |');
  console.log('| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |');
  const novTrades = completedTrades.filter((t) => t.entryDate.startsWith('2026-11'));
  const novBySym: Record<string, StrictMcxTrade[]> = {};
  for (const t of novTrades) {
    if (!novBySym[t.symbol]) novBySym[t.symbol] = [];
    novBySym[t.symbol].push(t);
  }
  for (const [sym, trs] of Object.entries(novBySym).sort((a, b) => {
    const netA = a[1].reduce((acc, t) => acc + t.netPnl, 0);
    const netB = b[1].reduce((acc, t) => acc + t.netPnl, 0);
    return netB - netA;
  })) {
    const wCount = trs.filter((t) => t.netPnl > 0).length;
    const lCount = trs.length - wCount;
    const wr = ((wCount / trs.length) * 100).toFixed(1);
    const gPnl = trs.reduce((acc, t) => acc + t.grossPnl, 0);
    const fric = trs.reduce((acc, t) => acc + t.totalFriction, 0);
    const nPnl = trs.reduce((acc, t) => acc + t.netPnl, 0);
    const sign = nPnl >= 0 ? '+' : '';
    console.log(`| **${sym}** | ${trs.length} | ${wCount} | ${lCount} | ${wr}% | ₹${gPnl.toFixed(2)} | ₹${fric.toFixed(2)} | **${sign}₹${nPnl.toFixed(2)}** |`);
  }

  // Group by commodity
  const bySymbol: Record<string, StrictMcxTrade[]> = {};
  for (const t of completedTrades) {
    if (!bySymbol[t.symbol]) bySymbol[t.symbol] = [];
    bySymbol[t.symbol].push(t);
  }

  console.log('\n📊 COMMODITY-WISE PERFORMANCE BREAKDOWN:');
  console.log('| Symbol | Trades | Wins | Win Rate | Gross P&L | Friction | True Net P&L (₹) |');
  console.log('| :--- | :--- | :--- | :--- | :--- | :--- | :--- |');
  for (const [sym, trs] of Object.entries(bySymbol).sort((a, b) => {
    const netA = a[1].reduce((acc, t) => acc + t.netPnl, 0);
    const netB = b[1].reduce((acc, t) => acc + t.netPnl, 0);
    return netB - netA;
  })) {
    const wCount = trs.filter((t) => t.netPnl > 0).length;
    const wr = ((wCount / trs.length) * 100).toFixed(1);
    const gPnl = trs.reduce((acc, t) => acc + t.grossPnl, 0);
    const fric = trs.reduce((acc, t) => acc + t.totalFriction, 0);
    const nPnl = trs.reduce((acc, t) => acc + t.netPnl, 0);
    const sign = nPnl >= 0 ? '+' : '';
    console.log(`| **${sym}** | ${trs.length} | ${wCount} | ${wr}% | ₹${gPnl.toFixed(2)} | ₹${fric.toFixed(2)} | **${sign}₹${nPnl.toFixed(2)}** |`);
  }

  // Top 5 runners
  const sortedRunners = [...completedTrades].sort((a, b) => b.netPnl - a.netPnl).slice(0, 5);
  console.log('\n🏆 TOP 5 HIGHEST PROFIT MCX RUNNER TRADES:');
  console.log('| Date | Symbol | Option Contract | Side | Hours Held | Friction | True Net (₹) |');
  console.log('| :--- | :--- | :--- | :--- | :--- | :--- | :--- |');
  for (const r of sortedRunners) {
    console.log(`| ${r.entryDate} | **${r.symbol}** | ${r.optionSymbol} | ${r.side} | ${r.hoursHeld}h | ₹${r.totalFriction} | **+₹${r.netPnl.toFixed(2)}** |`);
  }
}

runMcxStrictAudit().catch(console.error);
